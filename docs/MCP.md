# Emotion Engine MCP Server

Emotion Engine includes a zero-dependency local stdio MCP server for runtime/protocol tools.

This is not an Agent Harness management interface. Target refresh, doctor checks, repair, installed manifest checks, and sidecar projection drift detection belong to Agent Harness.

## Boundary

Use the Emotion Engine MCP server for:

- reading public runtime status
- building compact prompt-safe continuity summaries
- deciding whether a turn should be recorded with `record_policy`
- getting deterministic advisory appraisal output
- recording host-approved PAD turn updates
- applying pre-turn decay
- starting sessions
- settling agent-to-user trust
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
  --state .emotion-engine/codex-state.json
```

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

For Codex or Agent Harness project installs, register the bundled server against the Codex state file:

```bash
codex mcp add emotion-engine -- \
  python3 /path/to/project/.codex/skills/emotion-engine-codex/scripts/emotion_engine_mcp.py \
  --state /path/to/project/.emotion-engine/codex-state.json
```

Then verify:

```bash
codex mcp list
```

For Claude Code, add the same local stdio server:

```bash
claude mcp add --transport stdio emotion-engine -- \
  python3 /path/to/project/.codex/skills/emotion-engine-codex/scripts/emotion_engine_mcp.py \
  --state /path/to/project/.emotion-engine/codex-state.json
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
        "/path/to/project/.emotion-engine/codex-state.json"
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
| `emotion_engine_record_policy` | No | Decide whether a turn should be persisted under `light`, `always`, or `paused`. |
| `emotion_engine_appraise` | No | Return deterministic first-pass appraisal and PAD suggestion. Advisory only. |
| `emotion_engine_session_start` | Yes | Record the start of a meaningful session. |
| `emotion_engine_pre_turn_decay` | Yes | Apply small in-session drift before a turn. |
| `emotion_engine_record_turn` | Yes | Persist host/LLM-approved final PAD values and compact memory fields. |
| `emotion_engine_settle_trust` | Yes | Conservatively settle agent-to-user trust from recent evidence. |
| `emotion_engine_recent_log` | No | Read recent compact emotion log entries. |

## Minimal JSON-RPC Smoke Test

Start the server and send one JSON-RPC object per line:

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke-test","version":"0"}}}
{"jsonrpc":"2.0","id":2,"method":"tools/list"}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"emotion_engine_record_policy","arguments":{"message":"that migration was handled well","mode":"light","contexts":["milestone"]}}}
```

The `record_policy` call is side-effect free. It can return `record_turn` with a suggested appraisal and reply bias, but it does not write state.

## Host Flow

Recommended loop for an MCP-capable local agent:

1. Call `emotion_engine_summary` or `emotion_engine_status` to build compact context.
2. Call `emotion_engine_record_policy` before deciding whether a user turn should be persisted.
3. Let the host or LLM decide the final appraisal, PAD values, and compact memory.
4. Call `emotion_engine_record_turn` only for host-approved updates.
5. Call `emotion_engine_settle_trust` at a meaningful session or milestone close.

Do not expose raw PAD, trust, or compact logs to end users unless they explicitly ask for debugging details.
