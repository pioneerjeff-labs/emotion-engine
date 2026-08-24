# Emotion Engine For Pi Agent

This is the Pi Agent-compatible Agent Skill package for Emotion Engine.

It contains:

- `SKILL.md` for Pi's Agent Skills discovery.
- `scripts/pi_emotion.sh`, a wrapper that manages state path and initialization.
- `install.sh` for a self-contained manual installation.

When Pi installs the repository as a Git package, the wrapper uses the shared Emotion Engine core from that checkout. Manual install and zip packaging copy the core, state template, protocol schema, and license into the skill directory.

## Install

Preferred Pi package install from the repository root:

```bash
pi install git:github.com/pioneerjeff-labs/emotion-engine
```

Manual user-level skill install from this folder:

```bash
sh install.sh
```

Manual installation never migrates or binds state automatically. It runs a read-only activation check and prints the exact explicit migration or identity-binding command when state is not ready.

Default skill path:

```text
~/.pi/agent/skills/emotion-engine
```

Default personal state path:

```text
~/.pi/agent/emotion-engine/emotion-state.json
```

Projects with `.git` or `.pi` in the current or an ancestor directory use:

```text
.emotion-engine/pi-state.json
```

Override with:

```bash
export PI_SKILLS_DIR=/path/to/pi/skills
export PI_EMOTION_STATE=/path/to/emotion-state.json
```

## Use In Pi

Ask Pi naturally:

- "Use Emotion Engine and set the style to warm but clearly bounded."
- "What's the current Emotion Engine status?"
- "Preview safe Emotion Engine log compaction."

Or load it explicitly:

```text
/skill:emotion-engine status
```

The wrapper can also be tested directly:

```bash
scripts/pi_emotion.sh status
scripts/pi_emotion.sh configure --style "warm but not over-compliant"
scripts/pi_emotion.sh appraise "thank you, this is helpful"
```

The integration uses local files only. Pi still makes the contextual judgment and writes the final reply; Emotion Engine persists compact continuity guidance.
