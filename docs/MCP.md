# Emotion Engine MCP Server

Emotion Engine includes a zero-dependency local stdio MCP server for runtime/protocol tools.

This is not an Agent Harness management interface. Target refresh, doctor checks, repair, installed manifest checks, and sidecar projection drift detection belong to Agent Harness.

## Boundary

Use the Emotion Engine MCP server for:

- reading public runtime status
- checking schema, identity binding, and capabilities
- building compact prompt-safe continuity summaries
- applying the structured semantic and host-approval gate
- getting deterministic advisory appraisal output
- recording host-approved PAD turn updates
- applying pre-turn decay
- opening and closing native sessions idempotently
- settling agent-to-user trust from explicit evidence only
- auditing hard invariants separately from semantic warnings
- previewing migration, repair, and evidence-based trust reconciliation
- inspecting recent compact emotion log entries

Do not use this MCP server for:

- installing Emotion Engine into an agent target
- refreshing Codex or Claude sidecars
- repairing installed targets
- checking Agent Harness manifests
- replacing file-level locks, atomic writes, or backup recovery

The server wraps the existing `scripts/emotion_engine_utils.py` state helpers. Mutating tools use the same state-file lock, atomic write, backup, and recovery path as the CLI.

## Run Locally

For a generic Emotion Engine project, use the normal local state file:

```bash
python3 scripts/emotion_engine_mcp.py --state .emotion-engine/emotion-state.json
```

For Codex/Agent Harness project installs, point the server at the same state file as the Codex wrapper:

```bash
python3 .codex/skills/emotion-engine-codex/scripts/emotion_engine_mcp.py \
  --state .emotion-engine/codex-state.json \
  --locked-state \
  --managed-runtime
```

`--locked-state` requires `--state`, removes `state_file` from every tool schema, and rejects request-level path overrides. `--managed-runtime` additionally removes identity binding and migration tools so the owning installer can enforce its confirmation, backup, journal, and manifest transaction. Use both flags for installer-managed targets.

If `--state` is omitted, the server resolves state in this order:

1. tool argument `state_file`
2. `CODEX_EMOTION_STATE`
3. `EMOTION_ENGINE_STATE`
4. `.emotion-engine/codex-state.json` under `EMOTION_ENGINE_PROJECT_DIR` or the current directory when a Codex project marker is present
5. `.emotion-engine/emotion-state.json` under `EMOTION_ENGINE_PROJECT_DIR` or the current directory

Use an explicit `--state` in MCP client registration to avoid accidental state-file splits across clients.

The server speaks JSON-RPC over stdin/stdout, as local MCP clients expect.

## MCP Client Registration

Use absolute paths in client config when possible. Replace `/path/to/project` with your target project path and `/path/to/emotion-engine` with this repository checkout.

The helper script can register the local stdio server for common MCP clients:

```bash
python3 scripts/register_mcp_client.py codex --project-dir /path/to/project --state-profile codex
python3 scripts/register_mcp_client.py claude-code --project-dir /path/to/project --state-profile codex
python3 scripts/register_mcp_client.py mcp-json --project-dir /path/to/project --state-profile codex
```

Use `--dry-run` to preview the command or `.mcp.json` update first. Use `--state-profile generic` for non-Codex projects that should store state at `.emotion-engine/emotion-state.json`.

For Codex or Agent Harness project installs, register the bundled server against the Codex state file:

```bash
codex mcp add emotion-engine -- \
  python3 /path/to/project/.codex/skills/emotion-engine-codex/scripts/emotion_engine_mcp.py \
  --state /path/to/project/.emotion-engine/codex-state.json \
  --locked-state \
  --managed-runtime
```

Then verify:

```bash
codex mcp list
```

For Claude Code, add the same local stdio server:

```bash
claude mcp add --transport stdio emotion-engine -- \
  python3 /path/to/project/.codex/skills/emotion-engine-codex/scripts/emotion_engine_mcp.py \
  --state /path/to/project/.emotion-engine/codex-state.json \
  --locked-state \
  --managed-runtime
```

For Claude Desktop or a checked-in `.mcp.json`, use the standard `mcpServers` shape:

```json
{
  "mcpServers": {
    "emotion-engine": {
      "command": "python3",
      "args": [
        "/path/to/project/.codex/skills/emotion-engine-codex/scripts/emotion_engine_mcp.py",
        "--state",
        "/path/to/project/.emotion-engine/codex-state.json",
        "--locked-state",
        "--managed-runtime"
      ]
    }
  }
}
```

If you are not using a Codex/Agent Harness project install, point the client at the repository script and a generic state file instead:

```json
{
  "mcpServers": {
    "emotion-engine": {
      "command": "python3",
      "args": [
        "/path/to/emotion-engine/scripts/emotion_engine_mcp.py",
        "--state",
        "/path/to/project/.emotion-engine/emotion-state.json"
      ]
    }
  }
}
```

After changing MCP config, start a fresh client session or reload MCP servers so the native tool namespace is exposed. The server does not make MCP clients discover it automatically.

## Tools

| Tool | Mutates state | Purpose |
|---|---:|---|
| `emotion_engine_status` | No | Read public status, or raw state only when explicitly requested. |
| `emotion_engine_summary` | No | Return compact prompt-safe continuity guidance and recent compact memories. |
| `emotion_engine_capabilities` | No | Read schema, identity status, and capability declarations. |
| `emotion_engine_bind_identity` | Yes | Bind an unbound v3 packet once. |
| `emotion_engine_migrate_state` | Optional | Preview v2-to-v3 migration by default; apply only when requested with explicit identity. |
| `emotion_engine_record_policy` | No | Route structured task, relationship, self, or mixed events. |
| `emotion_engine_appraise` | No | Return deterministic first-pass appraisal and PAD suggestion. Advisory only. |
| `emotion_engine_session_start` | Yes | Idempotently open a native session using session and event ids. |
| `emotion_engine_session_end` | Yes | Idempotently close only the matching active session. |
| `emotion_engine_pre_turn_decay` | Yes | Apply guarded in-session drift. |
| `emotion_engine_record_turn` | Yes | Persist explicitly host-approved final PAD and optional trust evidence. |
| `emotion_engine_evaluate_and_record_turn` | Optional | Atomically gate and optionally record a structured turn. |
| `emotion_engine_settle_trust` | Optional | Settle a closed session only when eligible evidence exists. |
| `emotion_engine_recent_log` | No | Read recent compact emotion log entries. |
| `emotion_engine_audit_log` | No | Inspect log pressure plus invariant and semantic findings. |
| `emotion_engine_audit_state` | No | Check identity, lifecycle, idempotency, and evidence invariants. |
| `emotion_engine_repair_plan` | No | Return a dry-run plan without guessing ownership. |
| `emotion_engine_reconcile_trust` | Optional | Preview by default; apply only with an explicit baseline. |
| `emotion_engine_compact_log` | Optional | Preview safe compaction by default; mutates only when `apply` is `true`. |

## Minimal JSON-RPC Smoke Test

Start the server and send one JSON-RPC object per line:

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke-test","version":"0"}}}
{"jsonrpc":"2.0","id":2,"method":"tools/list"}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"emotion_engine_record_policy","arguments":{"message":"that migration was handled well","mode":"light","contexts":["milestone"]}}}
```

The `record_policy` call is side-effect free. This milestone example returns `respond_only` (or `route_host_memory` when a memory owner is supplied), never an emotional record.

## Host Flow

Recommended loop for an MCP-capable local agent:

1. Call `emotion_engine_capabilities`; migrate v2 explicitly and bind v3 identity before mutation. In a managed target, perform those actions through the owning installer instead of MCP.
2. Open the native session with unique `session_id` and `event_id`.
3. Call `emotion_engine_evaluate_and_record_turn` with `subject`, semantic `event_type`, and the host's explicit approval. Task checkpoints route to host memory.
4. Supply trust evidence only as an explicit, uniquely identified host-approved object.
5. Close the matching session, then settle once. With no eligible evidence, settlement is a no-op.

For long-running `always` mode agents, periodically call `emotion_engine_audit_log`. If low-value `pre_turn_decay` or neutral-turn pressure is high, call `emotion_engine_compact_log` first without `apply`, inspect the report, then call it with `apply: true` only when the host accepts the retention plan.

Do not expose raw PAD, trust, or compact logs to end users unless they explicitly ask for debugging details.

Emotion Engine retention tools do not choose where factual memory belongs. They may identify ordinary facts, stable preferences, or low-value continuity entries as storage candidates or retention noise, but the host runtime owns factual memory routing, retrieval, documents, and project-specific stores.
