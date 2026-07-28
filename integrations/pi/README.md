# Pi Agent Integration

This folder contains the Pi Agent-compatible package for Emotion Engine.

Pi implements the Agent Skills standard and can load this integration directly from the repository-level Pi package manifest.

## Install With Pi

Install the repository as a user-level Pi package:

```bash
pi install git:github.com/pioneerjeff-labs/emotion-engine
```

For a project-local install:

```bash
pi install -l git:github.com/pioneerjeff-labs/emotion-engine
```

After Pi reloads its resources, use natural language or:

```text
/skill:emotion-engine status
```

The package does not need a separate setup step. Its wrapper uses the shared core from the Pi-managed Git checkout and initializes state on first use.

## Manual Install

To copy a self-contained user skill into `~/.pi/agent/skills/`:

```bash
cd integrations/pi/emotion-engine
sh install.sh
```

Default state path:

```text
~/.pi/agent/emotion-engine/emotion-state.json
```

Inside a trusted Pi project, the wrapper instead uses:

```text
.emotion-engine/pi-state.json
```

Override the install or state path with:

```bash
export PI_SKILLS_DIR=/path/to/pi/skills
export PI_EMOTION_STATE=/path/to/emotion-state.json
```

## Build Zip

```bash
cd integrations/pi
./package_pi_skill.sh
```

This creates `emotion-engine-pi-skill.zip` for manual distribution.

The integration is local-only: no network calls, no telemetry, and no full transcript storage.
