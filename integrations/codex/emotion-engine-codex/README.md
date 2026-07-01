# Emotion Engine For Codex

This is the Codex-compatible package for Emotion Engine.

It contains:

- `SKILL.md` for Codex skills.
- `scripts/codex_emotion.sh`, a Codex wrapper that manages state path and initialization.
- `scripts/emotion_engine_mcp.py`, a local stdio MCP server for runtime/protocol tools.
- `scripts/nora_demo.py`, a prompt-packet demo for no-state/factual/low-trust/high-trust comparison.
- `install.sh` for personal Codex installation.

When installed or packaged, the shared Emotion Engine core, state template, protocol schema, and license are copied from the repository root.

## Install For Codex

From this folder:

```bash
sh install.sh
```

The installer creates a user-level Codex skill, not a bundled/system skill. It uses `CODEX_SKILLS_DIR` when set. Otherwise, it prefers an existing local `~/.codex/skills` directory and falls back to:

```text
~/.agents/skills/emotion-engine-codex
```

and stores personal state in the matching local home:

```text
~/.codex/emotion-engine/emotion-state.json
~/.agents/emotion-engine/emotion-state.json
```

Override state location with:

```bash
export CODEX_EMOTION_STATE=/path/to/emotion-state.json
```

## Use In Codex

Ask Codex naturally:

- "Enable Emotion Engine with a warm but not over-compliant style."
- "Tune it to be calmer."
- "Pause emotion logging."
- "What's the current emotion-engine status?"
- "Generate the Nora low-trust comparison prompt."

The skill maps those requests to:

```bash
scripts/codex_emotion.sh configure --style "warm but not over-compliant"
scripts/codex_emotion.sh tune "calmer"
scripts/codex_emotion.sh pause
scripts/codex_emotion.sh status
scripts/codex_emotion.sh nora-demo --packet low --reply-prompt
```

Agent Harness installs `scripts/codex_emotion.sh` as a project-root wrapper. If you only copied the skill folder manually, call the bundled script directly:

```bash
.codex/skills/emotion-engine-codex/scripts/codex_emotion.sh status
```

For MCP-capable local clients, use the bundled stdio server and point it at the same state file:

```bash
python3 .codex/skills/emotion-engine-codex/scripts/emotion_engine_mcp.py \
  --state .emotion-engine/codex-state.json
```

The MCP server exposes runtime/protocol tools only. Agent Harness owns target refresh, doctor, repair, manifest checks, and sidecar projection drift checks.

## Project-Local State

When used inside a project folder with `.git` or `.codex`, the wrapper stores state at:

```text
./.emotion-engine/codex-state.json
```

This keeps each project/character separate. Set `CODEX_EMOTION_STATE` if you want one shared state file.

## Package For Codex Skill Upload

From the parent `codex/` folder:

```bash
./package_codex_skill.sh
```

This creates:

```text
emotion-engine-codex-skill.zip
```

The zip contains the `emotion-engine-codex/` folder with `SKILL.md` at its root.

## Notes

This package uses local files only. It does not call an LLM, make network requests, or store full transcripts. Codex still decides the final reply; Emotion Engine persists compact continuity guidance.
