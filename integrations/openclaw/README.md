# OpenClaw Integration

This folder contains the OpenClaw-compatible package for Emotion Engine.

## Layout

```text
integrations/openclaw/
├── emotion-engine/
│   ├── SKILL.md
│   ├── README.md
│   ├── install.sh
│   ├── emotion-state-template.json
│   ├── LICENSE
│   └── scripts/
│       └── emotion_engine_utils.py
└── package_openclaw_skill.sh
```

## Install

From the repository root:

```bash
cd integrations/openclaw/emotion-engine
./install.sh
```

The installer copies the skill into your OpenClaw workspace:

```text
~/.openclaw/workspace/skills/emotion-engine
```

Override the workspace with:

```bash
export OPENCLAW_WORKSPACE=/path/to/openclaw/workspace
```

## Build Upload Zip

From the repository root:

```bash
cd integrations/openclaw
./package_openclaw_skill.sh
```

This creates `emotion-engine-openclaw-skill.zip`.
