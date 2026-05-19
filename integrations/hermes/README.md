# Hermes Integration

This folder contains the Hermes Agent-compatible package for Emotion Engine.

Hermes Skills use `SKILL.md` plus optional scripts and references. This integration keeps the shared core at the repository root and copies it into the generated/installed Hermes skill.
The repository root also includes `skills/emotion-engine`, a self-contained copy that Hermes can install directly from GitHub.

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

Published GitHub skill path:

```text
skills/emotion-engine/
├── SKILL.md
├── README.md
├── install.sh
├── scripts/
│   ├── hermes_emotion.sh
│   └── emotion_engine_utils.py
├── emotion-state-template.json
└── LICENSE
```

## Install From Skills Hub / GitHub

```bash
hermes skills install skills-sh/pioneerjeff-labs/emotion-engine/skills/emotion-engine
```

Fallback direct GitHub path:

```bash
hermes skills install pioneerjeff-labs/emotion-engine/skills/emotion-engine
```

Or add the repository as a custom tap:

```bash
hermes skills tap add pioneerjeff-labs/emotion-engine
hermes skills install pioneerjeff-labs/emotion-engine/skills/emotion-engine
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

## Prepare A Self-Contained Package

Hermes install sources expect a self-contained skill directory. The source skill
under `integrations/hermes/emotion-engine` keeps shared files at the repository
root, so prepare a self-contained copy first:

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

The tracked GitHub-installable copy lives at `skills/emotion-engine`. Refresh it
from `dist/hermes-hub/emotion-engine` before release if the shared engine
changes.

Note: `hermes skills publish --to github` creates a fork and pull request into
the target repository. For this project repository, direct GitHub installation
from `skills/emotion-engine` is the simpler public distribution path.

The skill uses local files only: no network calls, no telemetry, and no full
transcript storage.
