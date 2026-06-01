# OpenClaw Integration

This folder contains the OpenClaw-compatible package for Emotion Engine.

## Layout

```text
integrations/openclaw/
├── emotion-engine/
│   ├── SKILL.md
│   ├── README.md
│   ├── install.sh
└── package_openclaw_skill.sh
```

The shared core, license, state template, and protocol schema are kept once at the repository root. The installer and packaging script copy them into the installed/generated OpenClaw package.

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
