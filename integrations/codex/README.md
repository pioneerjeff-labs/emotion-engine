# Codex Integration

This folder contains the Codex-compatible package for Emotion Engine.

Codex skills use `SKILL.md` plus optional scripts. This integration keeps the shared core and protocol schema at the repository root and copies them into the generated/installed Codex skill.

## Layout

```text
integrations/codex/
├── emotion-engine-codex/
│   ├── SKILL.md
│   ├── README.md
│   ├── install.sh
│   └── scripts/
│       ├── codex_emotion.sh
│       ├── emotion_engine_mcp.py
│       ├── register_mcp_client.py
│       └── nora_demo.py
└── package_codex_skill.sh
```

## Install For Codex

```bash
cd integrations/codex/emotion-engine-codex
sh install.sh
```

The installer creates a user-level Codex skill, not a bundled/system skill. It uses `CODEX_SKILLS_DIR` when set. Otherwise, it prefers an existing local `~/.codex/skills` directory and falls back to:

```text
~/.agents/skills/emotion-engine-codex
```

Personal state defaults to the matching local home: `~/.codex/emotion-engine/emotion-state.json` when `~/.codex` is active, or `~/.agents/emotion-engine/emotion-state.json` for the `~/.agents` fallback.

Project-local Codex wrappers use `./.emotion-engine/codex-state.json`. Agent Harness targets use the same project-local state path.

Override with:

```bash
export CODEX_SKILLS_DIR=/path/to/codex/skills
export CODEX_EMOTION_STATE=/path/to/codex-state.json
```

For MCP-capable clients, register the bundled stdio server with an explicit state path. Codex/Agent Harness project targets should pass `--state .emotion-engine/codex-state.json`; see [../../docs/MCP.md](../../docs/MCP.md).

The helper script can register Codex, Claude Code, or a project `.mcp.json`:

```bash
python3 scripts/register_mcp_client.py codex --project-dir /path/to/project --state-profile codex
python3 scripts/register_mcp_client.py claude-code --project-dir /path/to/project --state-profile codex
python3 scripts/register_mcp_client.py mcp-json --project-dir /path/to/project --state-profile codex
```

## Build Zip

```bash
cd integrations/codex
./package_codex_skill.sh
```

This creates `emotion-engine-codex-skill.zip`.

The skill uses local files only: no network calls, no telemetry, and no full transcript storage.
