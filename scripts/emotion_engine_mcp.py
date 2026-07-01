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
SERVER_VERSION = "0.2.1"
DEFAULT_PROTOCOL_VERSION = "2024-11-05"


class JsonRpcError(Exception):
    def __init__(self, code, message, data=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


def resolve_state_file(arguments=None, default_state_file=None):
    arguments = arguments or {}
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


def load_state_for_tool(arguments=None, default_state_file=None):
    state_file = resolve_state_file(arguments, default_state_file)
    return state_file, engine.load_state(state_file)


def mutate_state_for_tool(arguments, default_state_file, mutator):
    state_file = resolve_state_file(arguments, default_state_file)
    ensure_state_parent(state_file)
    with engine.state_file_lock(state_file):
        state = engine.load_state_unlocked(state_file)
        state, result = mutator(state)
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
        "enabled": status["enabled"],
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


def call_tool(name, arguments=None, default_state_file=None):
    arguments = arguments or {}
    if not isinstance(arguments, dict):
        raise JsonRpcError(-32602, "Tool arguments must be an object")

    if name == "emotion_engine_status":
        state_file, state = load_state_for_tool(arguments, default_state_file)
        return {"state_file": state_file, "state": state if arguments.get("raw") else engine.public_status(state)}

    if name == "emotion_engine_summary":
        state_file, state = load_state_for_tool(arguments, default_state_file)
        limit = int(arguments.get("limit", 5) or 5)
        return {"state_file": state_file, "summary": compact_summary(state, limit=limit)}

    if name == "emotion_engine_record_policy":
        message = require_text(arguments, "message")
        state_file, state = load_state_for_tool(arguments, default_state_file)
        policy = engine.record_policy(
            state,
            message,
            mode=arguments.get("mode"),
            contexts=optional_contexts(arguments),
        )
        return {"state_file": state_file, "policy": policy}

    if name == "emotion_engine_appraise":
        message = require_text(arguments, "message")
        state_file, state = load_state_for_tool(arguments, default_state_file)
        return {"state_file": state_file, "appraisal": engine.appraise_message(state, message)}

    if name == "emotion_engine_session_start":
        def mutator(state):
            state = engine.session_start(state)
            return state, {
                "emotion": state["emotion"],
                "affective_pulse": state["affective_pulse"],
                "trust": state["trust"],
                "session_count": state["session_count"],
            }

        return mutate_state_for_tool(arguments, default_state_file, mutator)

    if name == "emotion_engine_pre_turn_decay":
        def mutator(state):
            state = engine.apply_in_session_decay(state)
            return state, {"emotion": state["emotion"], "affective_pulse": state["affective_pulse"]}

        return mutate_state_for_tool(arguments, default_state_file, mutator)

    if name == "emotion_engine_record_turn":
        pleasure = optional_float(arguments, "pleasure", "P", required=True)
        arousal = optional_float(arguments, "arousal", "A", required=True)
        dominance = optional_float(arguments, "dominance", "D", required=True)
        memory = memory_arguments(arguments)

        def mutator(state):
            state = engine.record_turn(state, pleasure, arousal, dominance, **memory)
            return state, {
                "emotion": state["emotion"],
                "affective_pulse": state["affective_pulse"],
                "turn": len(state["emotion_trajectory"]),
                "status": engine.public_status(state),
            }

        return mutate_state_for_tool(arguments, default_state_file, mutator)

    if name == "emotion_engine_settle_trust":
        def mutator(state):
            state, result = engine.settle_trust(state)
            return state, result

        return mutate_state_for_tool(arguments, default_state_file, mutator)

    if name == "emotion_engine_recent_log":
        state_file, state = load_state_for_tool(arguments, default_state_file)
        limit = int(arguments.get("limit", 5) or 5)
        return {"state_file": state_file, "events": state.get("emotion_log", [])[-limit:]}

    raise JsonRpcError(-32601, f"Unknown tool: {name}")


def tool_schema():
    state_arg = {
        "state_file": {
            "type": "string",
            "description": (
                "Optional path to emotion-engine-state/v2 JSON. Defaults to --state, "
                "CODEX_EMOTION_STATE, EMOTION_ENGINE_STATE, Codex project state, "
                "or .emotion-engine/emotion-state.json."
            ),
        }
    }
    return [
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
            "name": "emotion_engine_record_policy",
            "description": "Decide whether a turn should be recorded under light/always/paused mode. Side-effect free.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    **state_arg,
                    "message": {"type": "string"},
                    "mode": {"type": "string", "enum": ["light", "always", "paused"]},
                    "contexts": {"type": "array", "items": {"type": "string"}},
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
            "description": "Record the start of a meaningful local session.",
            "inputSchema": {"type": "object", "properties": state_arg},
        },
        {
            "name": "emotion_engine_pre_turn_decay",
            "description": "Apply small in-session drift before a turn.",
            "inputSchema": {"type": "object", "properties": state_arg},
        },
        {
            "name": "emotion_engine_record_turn",
            "description": "Persist a host/LLM-approved emotional turn update with compact memory fields.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    **state_arg,
                    "pleasure": {"type": "number", "minimum": -1, "maximum": 1},
                    "arousal": {"type": "number", "minimum": 0, "maximum": 1},
                    "dominance": {"type": "number", "minimum": 0, "maximum": 1},
                    "appraisal": {"type": "string"},
                    "situation": {"type": "string"},
                    "character_lens": {"type": "string"},
                    "relational_meaning": {"type": "string"},
                    "impact": {"type": "string"},
                    "open_loop": {"type": "boolean"},
                    "follow_up_bias": {"type": "string"},
                    "salience": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["pleasure", "arousal", "dominance"],
            },
        },
        {
            "name": "emotion_engine_settle_trust",
            "description": "Conservatively settle agent-to-user trust from recent evidence.",
            "inputSchema": {"type": "object", "properties": state_arg},
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
    ]


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


def handle_request(message, default_state_file=None):
    if not isinstance(message, dict):
        raise JsonRpcError(-32600, "Request must be a JSON object")
    request_id = message.get("id")
    method = message.get("method")
    params = message.get("params") or {}

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
        return jsonrpc_result(request_id, {"tools": tool_schema()})
    if method == "tools/call":
        name = params.get("name")
        if not isinstance(name, str) or not name:
            raise JsonRpcError(-32602, "tools/call requires a tool name")
        result = call_tool(name, params.get("arguments") or {}, default_state_file)
        return jsonrpc_result(request_id, tool_result(result))
    raise JsonRpcError(-32601, f"Method not found: {method}")


def serve_stdio(default_state_file=None, input_stream=None, output_stream=None):
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
            response = handle_request(message, default_state_file)
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
    args = parser.parse_args(argv)
    serve_stdio(default_state_file=args.state)


if __name__ == "__main__":
    main()
