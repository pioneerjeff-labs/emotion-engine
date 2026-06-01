# Claude Skill Integration

This folder contains the Claude-compatible package for Emotion Engine.

## Layout

```text
integrations/claude-skill/
├── emotion-engine/
│   ├── SKILL.md
│   ├── README.md
│   ├── install.sh
│   └── scripts/
│       └── claude_emotion.sh
└── package_claude_skill.sh
```

The shared core, license, state template, and protocol schema are kept once at the repository root. The installer and packaging script copy them into the installed/generated Claude package.

## Claude Code Install

```bash
cd integrations/claude-skill/emotion-engine
./install.sh
```

## Build Upload Zip

```bash
cd integrations/claude-skill
./package_claude_skill.sh
```

This creates `emotion-engine-claude-skill.zip`.

## State

Claude Code state defaults to `~/.claude/emotion-engine/emotion-state.json`, or project-local `./.emotion-engine/emotion-state.json` when used inside a project. Override with `CLAUDE_EMOTION_STATE`.
