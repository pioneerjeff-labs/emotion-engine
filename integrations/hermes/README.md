# Hermes Integration

This folder contains the Hermes Agent-compatible package for Emotion Engine.

Hermes Skills use `SKILL.md` plus optional scripts and references. This integration keeps the shared core at the repository root and copies it into the generated/installed Hermes skill.

## Layout

```text
integrations/hermes/
├── emotion-engine/
│   ├── SKILL.md
│   ├── README.md
│   ├── install.sh
│   └── scripts/
│       └── hermes_emotion.sh
└── package_hermes_skill.sh
```

## Install

```bash
cd integrations/hermes/emotion-engine
./install.sh
```

By default, this installs to:

```text
~/.hermes/skills/personal/emotion-engine
```

Override with:

```bash
export HERMES_SKILLS_DIR=/path/to/hermes/skills
export HERMES_EMOTION_STATE=/path/to/emotion-state.json
```

## Build Zip

```bash
cd integrations/hermes
./package_hermes_skill.sh
```

This creates `emotion-engine-hermes-skill.zip`.
