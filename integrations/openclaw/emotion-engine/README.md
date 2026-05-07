# Emotion Engine For OpenClaw

This is the OpenClaw-compatible package for Emotion Engine.

It contains:

- `SKILL.md` for OpenClaw.
- `scripts/emotion_engine_utils.py`, the shared Emotion Engine core.
- `emotion-state-template.json`.
- `install.sh` for local OpenClaw installation.

## Install

From this folder:

```bash
./install.sh
```

By default, this installs to:

```text
~/.openclaw/workspace/skills/emotion-engine
```

and stores state at:

```text
~/.openclaw/workspace/emotion-state.json
```

Override the OpenClaw workspace with:

```bash
export OPENCLAW_WORKSPACE=/path/to/openclaw/workspace
```

## Use In OpenClaw

After installation, ask naturally:

- "Enable Emotion Engine with a warm but not over-compliant style."
- "Tune it to be calmer."
- "Pause emotion logging."
- "What is the current Emotion Engine status?"

The skill maps those requests to the local state helper and keeps a compact continuity state between sessions.
