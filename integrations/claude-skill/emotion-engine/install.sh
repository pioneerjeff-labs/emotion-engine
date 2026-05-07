#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SKILLS_DIR=${CLAUDE_SKILLS_DIR:-"$HOME/.claude/skills"}
DEST="$SKILLS_DIR/emotion-engine"
STATE_FILE=${CLAUDE_EMOTION_STATE:-"$HOME/.claude/emotion-engine/emotion-state.json"}
PYTHON=${PYTHON:-python3}

mkdir -p "$SKILLS_DIR"
mkdir -p "$(dirname -- "$STATE_FILE")"

if [ "$SCRIPT_DIR" != "$DEST" ]; then
  mkdir -p "$DEST"
  cp -R "$SCRIPT_DIR"/. "$DEST"/
fi

chmod +x "$DEST/scripts/claude_emotion.sh" "$DEST/install.sh"

if [ ! -f "$STATE_FILE" ]; then
  "$PYTHON" "$DEST/scripts/emotion_engine_utils.py" init "$STATE_FILE" >/dev/null
  printf "Created state file: %s\n" "$STATE_FILE"
else
  printf "Existing state file preserved: %s\n" "$STATE_FILE"
fi

if [ -t 0 ]; then
  printf "Describe the vibe, or press Enter for default:\n> "
  read -r STYLE || true
  if [ "${STYLE:-}" ]; then
    CLAUDE_EMOTION_STATE="$STATE_FILE" "$DEST/scripts/claude_emotion.sh" configure --style "$STYLE"
  else
    CLAUDE_EMOTION_STATE="$STATE_FILE" "$DEST/scripts/claude_emotion.sh" status
  fi
else
  CLAUDE_EMOTION_STATE="$STATE_FILE" "$DEST/scripts/claude_emotion.sh" status
fi

printf "\nClaude Skill installed at: %s\n" "$DEST"
printf "State file: %s\n" "$STATE_FILE"
