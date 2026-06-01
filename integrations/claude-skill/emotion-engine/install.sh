#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../../.." && pwd)
SKILLS_DIR=${CLAUDE_SKILLS_DIR:-"$HOME/.claude/skills"}
DEST="$SKILLS_DIR/emotion-engine"
STATE_FILE=${CLAUDE_EMOTION_STATE:-"$HOME/.claude/emotion-engine/emotion-state.json"}
PYTHON=${PYTHON:-python3}

CORE_SCRIPT="$SCRIPT_DIR/scripts/emotion_engine_utils.py"
STATE_TEMPLATE="$SCRIPT_DIR/emotion-state-template.json"
SCHEMA_FILE="$SCRIPT_DIR/spec/emotion-state.schema.json"
LICENSE_FILE="$SCRIPT_DIR/LICENSE"

if [ ! -f "$CORE_SCRIPT" ]; then
  CORE_SCRIPT="$REPO_ROOT/scripts/emotion_engine_utils.py"
fi
if [ ! -f "$STATE_TEMPLATE" ]; then
  STATE_TEMPLATE="$REPO_ROOT/emotion-state-template.json"
fi
if [ ! -f "$SCHEMA_FILE" ]; then
  SCHEMA_FILE="$REPO_ROOT/spec/emotion-state.schema.json"
fi
if [ ! -f "$LICENSE_FILE" ]; then
  LICENSE_FILE="$REPO_ROOT/LICENSE"
fi

mkdir -p "$SKILLS_DIR"
mkdir -p "$(dirname -- "$STATE_FILE")"

if [ "$SCRIPT_DIR" != "$DEST" ]; then
  mkdir -p "$DEST/scripts" "$DEST/spec"
  cp "$SCRIPT_DIR/SKILL.md" "$DEST/"
  cp "$SCRIPT_DIR/README.md" "$DEST/"
  cp "$SCRIPT_DIR/install.sh" "$DEST/"
  cp "$SCRIPT_DIR/scripts/claude_emotion.sh" "$DEST/scripts/"
  cp "$CORE_SCRIPT" "$DEST/scripts/emotion_engine_utils.py"
  cp "$STATE_TEMPLATE" "$DEST/emotion-state-template.json"
  if [ -f "$SCHEMA_FILE" ]; then
    cp "$SCHEMA_FILE" "$DEST/spec/emotion-state.schema.json"
  fi
  if [ -f "$LICENSE_FILE" ]; then
    cp "$LICENSE_FILE" "$DEST/"
  fi
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
