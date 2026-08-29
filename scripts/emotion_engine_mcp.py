#!/usr/bin/env python3
"""Local stdio MCP server for Emotion Engine runtime tools.

This server exposes only Emotion Engine runtime/protocol behavior. Agent
installation, doctor checks, repair, and sidecar drift detection belong to
Agent Harness.
"""

import argparse
import json
import os
import sys

import emotion_engine_utils as engine


SERVER_NAME = "emotion-engine"
SERVER_VERSION = engine.ENGINE_VERSION
DEFAULT_PROTOCOL_VERSION = "2024-11-05"
MANAGED_RUNTIME_BLOCKED_TOOLS = {
    "emotion_engine_bind_identity",
    "emotion_engine_migrate_state",
}


class JsonRpcError(Exception):
    def __init__(self, code, message, data=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


def resolve_state_file(arguments=None, default_state_file=None):
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise JsonRpcError(-32602, "Tool arguments must be an object")
    raw = (
        arguments.get("state_file")
        or default_state_file
        or os.environ.get("CODEX_EMOTION_STATE")
        or os.environ.get("EMOTION_ENGINE_STATE")
    )
    if raw:
        return os.path.abspath(os.path.expanduser(os.fspath(raw)))
    project_dir = os.environ.get("EMOTION_ENGINE_PROJECT_DIR") or os.getcwd()
    codex_state = os.path.join(project_dir, ".emotion-engine", "codex-state.json")
    if os.path.exists(codex_state) or os.path.isdir(os.path.join(project_dir, ".codex")):
        return os.path.abspath(codex_state)
    return os.path.abspath(os.path.join(project_dir, ".emotion-engine", "emotion-state.json"))


def ensure_state_parent(state_file):
    directory = os.path.dirname(os.path.abspath(os.fspath(state_file)))
    if directory:
        os.makedirs(directory, exist_ok=True)


def load_state_for_tool(
    arguments=None,
    default_state_file=None,
    *,
    managed_runtime=False,
):
    state_file = resolve_state_file(arguments, default_state_file)
    if managed_runtime:
        ensure_state_parent(state_file)
        with engine.state_file_lock(state_file):
            engine.require_managed_state_file(state_file)
            return state_file, engine.load_state_unlocked(
                state_file,
                validate_raw_shape=True,
            )
    return state_file, engine.load_state(state_file)


def mutate_state_for_tool(
    arguments,
    default_state_file,
    mutator,
    allow_legacy=False,
    *,
    managed_runtime=False,
):
    state_file = resolve_state_file(arguments, default_state_file)
    ensure_state_parent(state_file)
    with engine.state_file_lock(state_file):
        if managed_runtime:
            engine.require_managed_state_file(state_file)
        state = engine.load_state_unlocked(
            state_file,
            validate_raw_shape=True,
        )
        if not allow_legacy and state.get("_schema") != engine.STATE_SCHEMA:
            raise JsonRpcError(-32602, "state migration required: v2 packets are read-only")
        missing_capabilities = engine.missing_state_capabilities(state)
        if not allow_legacy and missing_capabilities:
            raise JsonRpcError(
                -32042,
                "state capability upgrade required before writing",
                {"missing_capabilities": missing_capabilities},
            )
        if managed_runtime:
            engine.require_managed_runtime_writable(state_file, state)
        state, result = mutator(state)
        changed = bool(result.pop("_changed", True))
        if changed:
            engine.save_state_unlocked(state_file, state)
    return {"state_file": state_file, **result}


def compact_memory(entry):
    return {
        key: entry[key]
        for key in [
            "timestamp",
            "event_type",
            "appraisal",
            "situation",
            "relational_meaning",
            "impact",
            "follow_up_bias",
            "salience",
            "open_loop",
        ]
        if key in entry
    }


def compact_summary(state, limit=5):
    status = engine.public_status(state)
    recent = [compact_memory(entry) for entry in state.get("emotion_log", [])[-limit:]]
    return {
        "engine_version": status["engine_version"],
        "enabled": status["enabled"],
        "schema": status["schema"],
        "identity_status": status["identity_status"],
        "migration_required": status["migration_required"],
        "capabilities": status["capabilities"],
        "tone": status["summary"],
        "pulse": status["pulse"],
        "style": status["style"],
        "trust_tier": status["trust_tier"],
        "trust_progress_phrase": status["trust_progress_phrase"],
        "session_count": status["session_count"],
        "log_entries": status["log_entries"],
        "recent_memories": recent,
        "reply_rules": [
            "Do not expose PAD, trust, or raw state unless explicitly asked.",
            "Use recent compact memories as tone guidance, not factual recall.",
            "The host or LLM still decides the final emotional meaning.",
        ],
    }


def require_text(arguments, key):
    value = arguments.get(key)
    if not isinstance(value, str) or not value.strip():
        raise JsonRpcError(-32602, f"Missing required string argument: {key}")
    return value.strip()


def optional_contexts(arguments):
    contexts = arguments.get("contexts") or arguments.get("context") or []
    if isinstance(contexts, str):
        return [part.strip() for part in contexts.split(",") if part.strip()]
    if isinstance(contexts, list):
        return [str(item).strip() for item in contexts if str(item).strip()]
    raise JsonRpcError(-32602, "contexts must be a string or list of strings")


def optional_float(arguments, *keys, required=False):
    for key in keys:
        if key in arguments:
            try:
                return float(arguments[key])
            except (TypeError, ValueError) as exc:
                raise JsonRpcError(-32602, f"Argument {key} must be numeric") from exc
    if required:
        raise JsonRpcError(-32602, f"Missing required numeric argument: {keys[0]}")
    return None


def memory_arguments(arguments):
    return {
        "appraisal": arguments.get("appraisal"),
        "situation": arguments.get("situation"),
        "character_lens": arguments.get("character_lens") or arguments.get("lens"),
        "relational_meaning": arguments.get("relational_meaning") or arguments.get("meaning"),
        "impact": arguments.get("impact"),
        "open_loop": arguments.get("open_loop"),
        "follow_up_bias": arguments.get("follow_up_bias") or arguments.get("follow_up"),
        "salience": arguments.get("salience"),
    }


def call_tool(name, arguments=None, default_state_file=None, *, managed_runtime=False):
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise JsonRpcError(-32602, "Tool arguments must be an object")

    def load_tool_state():
        return load_state_for_tool(
            arguments,
            default_state_file,
            managed_runtime=managed_runtime,
        )

    def mutate_tool_state(mutator, allow_legacy=False):
        return mutate_state_for_tool(
            arguments,
            default_state_file,
            mutator,
            allow_legacy=allow_legacy,
            managed_runtime=managed_runtime,
        )

    if name == "emotion_engine_status":
        state_file, state = load_tool_state()
        return {"state_file": state_file, "state": state if arguments.get("raw") else engine.public_status(state)}

    if name == "emotion_engine_summary":
        state_file, state = load_tool_state()
        limit = int(arguments.get("limit", 5) or 5)
        return {"state_file": state_file, "summary": compact_summary(state, limit=limit)}

    if name == "emotion_engine_capabilities":
        state_file, state = load_tool_state()
        return {
            "state_file": state_file,
            "engine_version": engine.ENGINE_VERSION,
            "schema": state.get("_schema"),
            "capabilities": list(state.get("capabilities", [])),
            "identity_status": state.get("identity", {}).get("status"),
            "migration_required": state.get("_schema") != engine.STATE_SCHEMA,
        }

    if name == "emotion_engine_bind_identity":
        def mutator(state):
            state, result = engine.bind_state_identity(
                state,
                require_text(arguments, "character_id"),
                require_text(arguments, "relationship_id"),
            )
            result["_changed"] = result["status"] == "bound"
            return state, result

        return mutate_tool_state(mutator)

    if name == "emotion_engine_migrate_state":
        apply = arguments.get("apply") is True

        def mutator(state):
            migrated, result = engine.migrate_state_v2(
                state,
                require_text(arguments, "character_id"),
                require_text(arguments, "relationship_id"),
                state_id=arguments.get("state_id"),
            )
            result["dry_run"] = not apply
            result["_changed"] = apply and result["status"] == "migration_ready"
            if result["_changed"]:
                result["status"] = "migrated"
            return migrated if apply else state, result

        return mutate_tool_state(mutator, allow_legacy=True)

    if name == "emotion_engine_record_policy":
        message = require_text(arguments, "message")
        state_file, state = load_tool_state()
        policy = engine.record_policy(
            state,
            message,
            mode=arguments.get("mode"),
            contexts=optional_contexts(arguments),
            subject=arguments.get("subject"),
            event_type=arguments.get("event_type"),
            host_approved=arguments.get("host_approved") is True,
            memory_owner=arguments.get("memory_owner"),
            source=arguments.get("source") or "model_inferred",
        )
        return {"state_file": state_file, "policy": policy}

    if name == "emotion_engine_appraise":
        message = require_text(arguments, "message")
        state_file, state = load_tool_state()
        return {"state_file": state_file, "appraisal": engine.appraise_message(state, message)}

    if name == "emotion_engine_session_start":
        def mutator(state):
            state, result = engine.session_start(
                state,
                require_text(arguments, "session_id"),
                require_text(arguments, "event_id"),
                occurred_at=arguments.get("occurred_at"),
                character_id=require_text(arguments, "character_id"),
                relationship_id=require_text(arguments, "relationship_id"),
            )
            result["_changed"] = result["status"] == "started"
            return state, result

        return mutate_tool_state(mutator)

    if name == "emotion_engine_session_end":
        def mutator(state):
            state, result = engine.session_end(
                state,
                require_text(arguments, "session_id"),
                require_text(arguments, "event_id"),
                occurred_at=arguments.get("occurred_at"),
                character_id=require_text(arguments, "character_id"),
                relationship_id=require_text(arguments, "relationship_id"),
            )
            result["_changed"] = result["status"] == "closed"
            return state, result

        return mutate_tool_state(mutator)

    if name == "emotion_engine_pre_turn_decay":
        def mutator(state):
            state, result = engine.pre_turn_decay(
                state,
                session_id=require_text(arguments, "session_id"),
                event_id=require_text(arguments, "event_id"),
                character_id=require_text(arguments, "character_id"),
                relationship_id=require_text(arguments, "relationship_id"),
            )
            result["_changed"] = result["status"] == "applied"
            result["emotion"] = state["emotion"]
            result["affective_pulse"] = state["affective_pulse"]
            return state, result

        return mutate_tool_state(mutator)

    if name == "emotion_engine_record_turn":
        pleasure = optional_float(arguments, "pleasure", "P", required=True)
        arousal = optional_float(arguments, "arousal", "A", required=True)
        dominance = optional_float(arguments, "dominance", "D", required=True)
        memory = memory_arguments(arguments)

        def mutator(state):
            state, result = engine.record_turn(
                state,
                pleasure,
                arousal,
                dominance,
                session_id=require_text(arguments, "session_id"),
                event_id=require_text(arguments, "event_id"),
                subject=arguments.get("subject") or "relationship",
                semantic_event_type=arguments.get("event_type"),
                trust_evidence=arguments.get("trust_evidence"),
                host_approved=arguments.get("host_approved") is True,
                character_id=require_text(arguments, "character_id"),
                relationship_id=require_text(arguments, "relationship_id"),
                **memory,
            )
            result["_changed"] = result["status"] == "recorded"
            result["emotion"] = state["emotion"]
            result["affective_pulse"] = state["affective_pulse"]
            result["status_summary"] = engine.public_status(state)
            return state, result

        return mutate_tool_state(mutator)

    if name == "emotion_engine_settle_trust":
        def mutator(state):
            state, result = engine.settle_trust(
                state,
                require_text(arguments, "session_id"),
                require_text(arguments, "event_id"),
                character_id=require_text(arguments, "character_id"),
                relationship_id=require_text(arguments, "relationship_id"),
            )
            result["_changed"] = result["status"] == "settled"
            return state, result

        return mutate_tool_state(mutator)

    if name == "emotion_engine_evaluate_and_record_turn":
        event = arguments.get("event")
        if not isinstance(event, dict):
            raise JsonRpcError(-32602, "event must be an object")

        def mutator(state):
            state, result = engine.evaluate_and_record_turn(
                state,
                event,
                p=optional_float(arguments, "pleasure", "P"),
                a=optional_float(arguments, "arousal", "A"),
                d=optional_float(arguments, "dominance", "D"),
                memory=memory_arguments(arguments),
                mode=arguments.get("mode"),
                character_id=arguments.get("character_id"),
                relationship_id=arguments.get("relationship_id"),
            )
            result["_changed"] = result["status"] in {"recorded", "state_only"}
            return state, result

        return mutate_tool_state(mutator)

    if name == "emotion_engine_recent_log":
        state_file, state = load_tool_state()
        limit = int(arguments.get("limit", 5) or 5)
        return {"state_file": state_file, "events": state.get("emotion_log", [])[-limit:]}

    if name == "emotion_engine_audit_log":
        state_file, state = load_tool_state()
        return {"state_file": state_file, "audit": engine.audit_emotion_log(state)}

    if name == "emotion_engine_audit_state":
        state_file, state = load_tool_state()
        return {"state_file": state_file, "audit": engine.audit_state_integrity(state)}

    if name == "emotion_engine_repair_plan":
        state_file, state = load_tool_state()
        return {"state_file": state_file, "plan": engine.repair_plan(state)}

    if name == "emotion_engine_reconcile_trust":
        apply = arguments.get("apply") is True

        def mutator(state):
            state, result = engine.reconcile_trust_from_evidence(
                state,
                baseline_trust=arguments.get("baseline_trust"),
                apply=apply,
            )
            result["_changed"] = result["status"] == "reconciled"
            return state, result

        return mutate_tool_state(mutator)

    if name == "emotion_engine_compact_log":
        apply = bool(arguments.get("apply", False))
        if not apply:
            state_file, state = load_tool_state()
            _, report = engine.compact_emotion_log(state)
            report["applied"] = False
            return {"state_file": state_file, "report": report}

        def mutator(state):
            state, report = engine.compact_emotion_log(state)
            report["applied"] = True
            report["status"] = engine.public_status(state)
            return state, {"report": report}

        return mutate_tool_state(mutator)

    raise JsonRpcError(-32601, f"Unknown tool: {name}")


def tool_schema(locked_state=False, managed_runtime=False):
    state_arg = {} if locked_state else {
        "state_file": {
            "type": "string",
            "description": (
                "Optional path to Emotion Engine state JSON. v2 is read-only until explicit migration. Defaults to --state, "
                "CODEX_EMOTION_STATE, EMOTION_ENGINE_STATE, Codex project state, "
                "or .emotion-engine/emotion-state.json."
            ),
        }
    }
    lifecycle = {
        "session_id": {"type": "string"},
        "event_id": {"type": "string"},
        "occurred_at": {"type": "string"},
    }
    identity = {
        "character_id": {"type": "string"},
        "relationship_id": {"type": "string"},
    }
    memory = {
        "appraisal": {"type": "string"},
        "situation": {"type": "string"},
        "character_lens": {"type": "string"},
        "relational_meaning": {"type": "string"},
        "impact": {"type": "string"},
        "open_loop": {"type": "boolean"},
        "follow_up_bias": {"type": "string"},
        "salience": {"type": "number", "minimum": 0, "maximum": 1},
    }
    pad = {
        "pleasure": {"type": "number", "minimum": -1, "maximum": 1},
        "arousal": {"type": "number", "minimum": 0, "maximum": 1},
        "dominance": {"type": "number", "minimum": 0, "maximum": 1},
    }
    trust_evidence = {
        "oneOf": [
            {"type": "object"},
            {"type": "array", "items": {"type": "object"}},
        ],
        "description": "Explicit host-approved evidence with evidence_id, evidence_type, and eligible=true.",
    }
    tools = [
        {
            "name": "emotion_engine_status",
            "description": "Read public Emotion Engine status; raw state is for debugging only.",
            "inputSchema": {
                "type": "object",
                "properties": {**state_arg, "raw": {"type": "boolean"}},
            },
        },
        {
            "name": "emotion_engine_summary",
            "description": "Return compact prompt-safe continuity guidance and recent compact memories.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    **state_arg,
                    "limit": {"type": "integer", "minimum": 0, "maximum": 20},
                },
            },
        },
        {
            "name": "emotion_engine_capabilities",
            "description": "Read state schema, identity binding status, and capability declarations.",
            "inputSchema": {"type": "object", "properties": state_arg},
        },
        {
            "name": "emotion_engine_bind_identity",
            "description": "Bind an unbound v3 state to one character and relationship. Rebinding is rejected.",
            "inputSchema": {
                "type": "object",
                "properties": {**state_arg, **identity},
                "required": ["character_id", "relationship_id"],
            },
        },
        {
            "name": "emotion_engine_migrate_state",
            "description": "Preview or explicitly apply v2-to-v3 migration. Ownership is never inferred.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    **state_arg, **identity,
                    "state_id": {"type": "string"},
                    "apply": {"type": "boolean", "default": False},
                },
                "required": ["character_id", "relationship_id"],
            },
        },
        {
            "name": "emotion_engine_record_policy",
            "description": "Apply the side-effect-free semantic and host-approval gate.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    **state_arg,
                    "message": {"type": "string"},
                    "mode": {"type": "string", "enum": ["light", "always", "paused"]},
                    "contexts": {"type": "array", "items": {"type": "string"}},
                    "subject": {"type": "string", "enum": ["task", "relationship", "self", "mixed"]},
                    "event_type": {"type": "string", "enum": sorted(engine.POLICY_EVENT_TYPES)},
                    "host_approved": {"type": "boolean"},
                    "memory_owner": {"type": "string"},
                    "source": {"type": "string"},
                },
                "required": ["message"],
            },
        },
        {
            "name": "emotion_engine_appraise",
            "description": "Return deterministic first-pass appraisal and PAD suggestion. Advisory only.",
            "inputSchema": {
                "type": "object",
                "properties": {**state_arg, "message": {"type": "string"}},
                "required": ["message"],
            },
        },
        {
            "name": "emotion_engine_session_start",
            "description": "Idempotently open one explicitly identified session.",
            "inputSchema": {
                "type": "object", "properties": {**state_arg, **lifecycle, **identity},
                "required": ["session_id", "event_id", "character_id", "relationship_id"],
            },
        },
        {
            "name": "emotion_engine_session_end",
            "description": "Idempotently close the matching active session.",
            "inputSchema": {
                "type": "object", "properties": {**state_arg, **lifecycle, **identity},
                "required": ["session_id", "event_id", "character_id", "relationship_id"],
            },
        },
        {
            "name": "emotion_engine_pre_turn_decay",
            "description": "Apply small in-session drift before a turn.",
            "inputSchema": {
                "type": "object", "properties": {**state_arg, **lifecycle, **identity},
                "required": ["session_id", "event_id", "character_id", "relationship_id"],
            },
        },
        {
            "name": "emotion_engine_record_turn",
            "description": "Persist a host/LLM-approved emotional turn update with compact memory fields.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    **state_arg, **lifecycle, **identity, **pad, **memory,
                    "subject": {"type": "string", "enum": ["task", "relationship", "self", "mixed"]},
                    "event_type": {"type": "string"},
                    "trust_evidence": trust_evidence,
                    "host_approved": {"type": "boolean", "const": True},
                },
                "required": ["session_id", "event_id", "character_id", "relationship_id", "pleasure", "arousal", "dominance", "host_approved"],
            },
        },
        {
            "name": "emotion_engine_evaluate_and_record_turn",
            "description": "Atomically apply semantic ownership, host approval, idempotency, and optional emotion recording.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    **state_arg, **identity, **pad, **memory,
                    "mode": {"type": "string", "enum": ["light", "always", "paused"]},
                    "event": {
                        "type": "object",
                        "properties": {
                            **lifecycle,
                            "message": {"type": "string"},
                            "subject": {"type": "string", "enum": ["task", "relationship", "self", "mixed"]},
                            "event_type": {"type": "string", "enum": sorted(engine.POLICY_EVENT_TYPES)},
                            "host_approved": {"type": "boolean"},
                            "memory_owner": {"type": "string"},
                            "source": {"type": "string"},
                            "trust_evidence": trust_evidence,
                        },
                        "required": ["session_id", "event_id", "subject", "event_type", "host_approved"],
                    },
                },
                "required": ["event", "character_id", "relationship_id"],
            },
        },
        {
            "name": "emotion_engine_settle_trust",
            "description": "Settle a closed session once from explicit unconsumed trust evidence only.",
            "inputSchema": {
                "type": "object", "properties": {**state_arg, **lifecycle, **identity},
                "required": ["session_id", "event_id", "character_id", "relationship_id"],
            },
        },
        {
            "name": "emotion_engine_recent_log",
            "description": "Read recent compact emotion log entries.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    **state_arg,
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                },
            },
        },
        {
            "name": "emotion_engine_audit_log",
            "description": "Inspect retention plus hard invariants and heuristic semantic warnings.",
            "inputSchema": {"type": "object", "properties": state_arg},
        },
        {
            "name": "emotion_engine_audit_state",
            "description": "Check identity, lifecycle, evidence, and idempotency invariants without mutation.",
            "inputSchema": {"type": "object", "properties": state_arg},
        },
        {
            "name": "emotion_engine_repair_plan",
            "description": "Return a dry-run repair plan without inferring ownership or changing state.",
            "inputSchema": {"type": "object", "properties": state_arg},
        },
        {
            "name": "emotion_engine_reconcile_trust",
            "description": "Preview trust reconstruction from evidence; apply only with an explicit baseline.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    **state_arg,
                    "baseline_trust": {"type": "number", "minimum": 0.05, "maximum": 1},
                    "apply": {"type": "boolean", "default": False},
                },
                "required": ["baseline_trust"],
            },
        },
        {
            "name": "emotion_engine_compact_log",
            "description": "Preview or apply safe low-value emotion_log compaction. Defaults to dry-run.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    **state_arg,
                    "apply": {"type": "boolean", "description": "When true, write the compacted log with the normal state backup path."},
                },
            },
        },
    ]
    if managed_runtime:
        tools = [
            tool for tool in tools
            if tool.get("name") not in MANAGED_RUNTIME_BLOCKED_TOOLS
        ]
    return tools


def jsonrpc_result(request_id, result):
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def jsonrpc_error(request_id, error):
    payload = {"code": error.code, "message": error.message}
    if error.data is not None:
        payload["data"] = error.data
    return {"jsonrpc": "2.0", "id": request_id, "error": payload}


def tool_result(value):
    return {
        "content": [{"type": "text", "text": json.dumps(value, indent=2, ensure_ascii=False)}],
        "structuredContent": value,
        "isError": False,
    }


def handle_request(
    message,
    default_state_file=None,
    locked_state=False,
    managed_runtime=False,
):
    if not isinstance(message, dict):
        raise JsonRpcError(-32600, "Request must be a JSON object")
    if message.get("jsonrpc") != "2.0":
        raise JsonRpcError(-32600, "Request must declare jsonrpc 2.0")
    request_id = message.get("id")
    method = message.get("method")
    params = message.get("params")
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise JsonRpcError(-32602, "Request params must be an object")

    if method == "notifications/initialized" or (
        request_id is None and str(method).startswith("notifications/")
    ):
        return None
    if method == "initialize":
        protocol_version = params.get("protocolVersion") or DEFAULT_PROTOCOL_VERSION
        return jsonrpc_result(request_id, {
            "protocolVersion": protocol_version,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })
    if method == "ping":
        return jsonrpc_result(request_id, {})
    if method == "tools/list":
        return jsonrpc_result(request_id, {
            "tools": tool_schema(
                locked_state=locked_state,
                managed_runtime=managed_runtime,
            )
        })
    if method == "tools/call":
        if "id" not in message or request_id is None:
            raise JsonRpcError(-32600, "tools/call requires a non-null request id")
        name = params.get("name")
        if not isinstance(name, str) or not name:
            raise JsonRpcError(-32602, "tools/call requires a tool name")
        arguments = params.get("arguments")
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            raise JsonRpcError(-32602, "Tool arguments must be an object")
        if locked_state and "state_file" in arguments:
            raise JsonRpcError(
                -32602,
                "state_file is fixed by the locked MCP server and cannot be overridden",
            )
        if managed_runtime and name in MANAGED_RUNTIME_BLOCKED_TOOLS:
            raise JsonRpcError(
                -32601,
                "tool is disabled in managed runtime mode; use the owning installer transaction",
            )
        try:
            result = call_tool(
                name,
                arguments,
                default_state_file,
                managed_runtime=managed_runtime,
            )
        except engine.ManagedStateError as exc:
            state_file = resolve_state_file(arguments, default_state_file)
            raise JsonRpcError(
                -32043,
                "Managed Emotion Engine state is not writable",
                exc.as_dict(state_file),
            ) from exc
        except ValueError as exc:
            raise JsonRpcError(-32602, str(exc)) from exc
        return jsonrpc_result(request_id, tool_result(result))
    raise JsonRpcError(-32601, f"Method not found: {method}")


def serve_stdio(
    default_state_file=None,
    input_stream=None,
    output_stream=None,
    locked_state=False,
    managed_runtime=False,
):
    input_stream = input_stream or sys.stdin
    output_stream = output_stream or sys.stdout
    for line in input_stream:
        line = line.strip()
        if not line:
            continue
        request_id = None
        try:
            message = json.loads(line)
            request_id = message.get("id") if isinstance(message, dict) else None
            response = handle_request(
                message,
                default_state_file,
                locked_state=locked_state,
                managed_runtime=managed_runtime,
            )
        except json.JSONDecodeError as exc:
            response = jsonrpc_error(None, JsonRpcError(-32700, "Parse error", str(exc)))
        except JsonRpcError as exc:
            response = jsonrpc_error(request_id, exc)
        except Exception as exc:  # pragma: no cover
            response = jsonrpc_error(request_id, JsonRpcError(-32603, "Internal error", str(exc)))
        if response is not None:
            output_stream.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
            output_stream.flush()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the local Emotion Engine stdio MCP server.")
    parser.add_argument("--state", help="default state file for MCP tool calls")
    parser.add_argument(
        "--locked-state",
        action="store_true",
        help="require --state and reject request-level state_file overrides",
    )
    parser.add_argument(
        "--managed-runtime",
        action="store_true",
        help="hide identity binding and migration tools owned by the installer transaction",
    )
    args = parser.parse_args(argv)
    if args.locked_state and not args.state:
        parser.error("--locked-state requires --state")
    if args.managed_runtime and (not args.locked_state or not args.state):
        parser.error("--managed-runtime requires --locked-state and --state")
    serve_stdio(
        default_state_file=args.state,
        locked_state=args.locked_state,
        managed_runtime=args.managed_runtime,
    )


if __name__ == "__main__":
    main()
