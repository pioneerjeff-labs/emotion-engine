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
├── package_hermes_skill.sh
└── prepare_hermes_hub_skill.sh
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

## Prepare For HermesHub

HermesHub expects a self-contained skill directory. The source skill under
`integrations/hermes/emotion-engine` keeps shared files at the repository root,
so prepare a publishable copy first:

```bash
cd integrations/hermes
./prepare_hermes_hub_skill.sh
```

This creates:

```text
dist/hermes-hub/emotion-engine/
├── SKILL.md
├── README.md
├── install.sh
├── scripts/
│   ├── hermes_emotion.sh
│   └── emotion_engine_utils.py
├── emotion-state-template.json
└── LICENSE
```

Publish from a machine with Hermes Agent installed:

```bash
hermes skills publish dist/hermes-hub/emotion-engine \
  --to github \
  --repo pioneerjeff-labs/emotion-engine
```

The skill uses local files only: no network calls, no telemetry, and no full
transcript storage.
