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

Override with:

```bash
export CODEX_SKILLS_DIR=/path/to/codex/skills
export CODEX_EMOTION_STATE=/path/to/emotion-state.json
```

## Build Zip

```bash
cd integrations/codex
./package_codex_skill.sh
```

This creates `emotion-engine-codex-skill.zip`.

The skill uses local files only: no network calls, no telemetry, and no full transcript storage.
