# Emotion Engine For Hermes

Hermes-compatible packaging for Emotion Engine.

It contains:

- `SKILL.md` for Hermes Skills.
- `scripts/hermes_emotion.sh`, a wrapper that manages state path and initialization.
- `install.sh` for local Hermes installation.

The shared core script, state template, and license are copied from the repository root during install/package.

## Install

From this folder:

```bash
./install.sh
```

Default install path:

```text
~/.hermes/skills/personal/emotion-engine
```

Default state path:

```text
~/.hermes/emotion-engine/emotion-state.json
```

Override with:

```bash
export HERMES_SKILLS_DIR=/path/to/hermes/skills
export HERMES_EMOTION_STATE=/path/to/emotion-state.json
```

## Use In Hermes

Once installed, use the slash command or natural language:

```text
/emotion-engine status
```

or:

```text
Use Emotion Engine and set the style to warm but clearly bounded.
```

The wrapper can also be tested directly:

```bash
scripts/hermes_emotion.sh status
scripts/hermes_emotion.sh configure --style "warm but not over-compliant"
scripts/hermes_emotion.sh appraise "thank you, this is helpful"
```

## Package

From `integrations/hermes/`:

```bash
./package_hermes_skill.sh
```

This creates `emotion-engine-hermes-skill.zip`.
