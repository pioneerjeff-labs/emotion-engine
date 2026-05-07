# Emotion Engine For Claude

This is the Claude-compatible package for Emotion Engine.

It contains:

- `SKILL.md` for Claude Skills.
- `scripts/claude_emotion.sh`, a Claude Code wrapper that manages state path and initialization.
- `install.sh` for personal Claude Code installation.

When installed or packaged, the shared Emotion Engine core, state template, and license are copied from the repository root.

## Install For Claude Code

From this folder:

```bash
./install.sh
```

By default, this installs to:

```text
~/.claude/skills/emotion-engine
```

and stores personal state at:

```text
~/.claude/emotion-engine/emotion-state.json
```

Override state location with:

```bash
export CLAUDE_EMOTION_STATE=/path/to/emotion-state.json
```

## Use In Claude Code

Ask Claude naturally:

- "Enable Emotion Engine with a warm but not over-compliant style."
- "Tune it to be calmer."
- "Pause emotion logging."
- "What's the current emotion-engine status?"

The skill maps those requests to:

```bash
scripts/claude_emotion.sh configure --style "warm but not over-compliant"
scripts/claude_emotion.sh tune "calmer"
scripts/claude_emotion.sh pause
scripts/claude_emotion.sh status
```

## Project-Local State

When used inside a project folder with `.git` or `.claude`, the wrapper stores state at:

```text
./.emotion-engine/emotion-state.json
```

This keeps each project/character separate. Set `CLAUDE_EMOTION_STATE` if you want one shared state file.

## Package For Claude Skills Upload

From the parent `claude-skill/` folder:

```bash
./package_claude_skill.sh
```

This creates:

```text
emotion-engine-claude-skill.zip
```

The zip contains the `emotion-engine/` folder with `SKILL.md` at its root.

## Notes

For Claude Code, state can persist locally. For web-uploaded Claude Skills, persistence depends on the host environment and may not behave like a long-lived local file. Use Claude Code for the most reliable personal continuity workflow.
