#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SKILLS_DIR=${HERMES_SKILLS_DIR:-"$HOME/.hermes/skills"}
DEST=${HERMES_SKILL_DEST:-"$SKILLS_DIR/personal/emotion-engine"}
STATE_FILE=${HERMES_EMOTION_STATE:-"$HOME/.hermes/emotion-engine/emotion-state.json"}
PYTHON=${PYTHON:-python3}

CORE_SCRIPT="$SCRIPT_DIR/scripts/emotion_engine_utils.py"
STATE_TEMPLATE="$SCRIPT_DIR/emotion-state-template.json"
SCHEMA_FILE="$SCRIPT_DIR/spec/emotion-state.schema.json"

if [ ! -f "$CORE_SCRIPT" ]; then
  printf "Emotion Engine core not found in package: %s\n" "$CORE_SCRIPT" >&2
  exit 1
fi
if [ ! -f "$STATE_TEMPLATE" ]; then
  printf "Emotion Engine state template not found in package: %s\n" "$STATE_TEMPLATE" >&2
  exit 1
fi

mkdir -p "$DEST/scripts" "$DEST/spec"
mkdir -p "$(dirname -- "$STATE_FILE")"

if [ "$SCRIPT_DIR" != "$DEST" ]; then
  cp "$SCRIPT_DIR/SKILL.md" "$DEST/"
  cp "$SCRIPT_DIR/README.md" "$DEST/"
  cp "$SCRIPT_DIR/install.sh" "$DEST/"
  cp "$SCRIPT_DIR/scripts/hermes_emotion.sh" "$DEST/scripts/"
  cp "$CORE_SCRIPT" "$DEST/scripts/emotion_engine_utils.py"
  cp "$STATE_TEMPLATE" "$DEST/emotion-state-template.json"
  if [ -f "$SCHEMA_FILE" ]; then
    cp "$SCHEMA_FILE" "$DEST/spec/emotion-state.schema.json"
  fi
  if [ -f "$SCRIPT_DIR/LICENSE" ]; then
    cp "$SCRIPT_DIR/LICENSE" "$DEST/"
  fi
fi

chmod +x "$DEST/scripts/hermes_emotion.sh" "$DEST/install.sh"

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
    HERMES_EMOTION_STATE="$STATE_FILE" "$DEST/scripts/hermes_emotion.sh" configure --style "$STYLE"
  else
    HERMES_EMOTION_STATE="$STATE_FILE" "$DEST/scripts/hermes_emotion.sh" status
  fi
else
  HERMES_EMOTION_STATE="$STATE_FILE" "$DEST/scripts/hermes_emotion.sh" status
fi

printf "\nHermes Skill installed at: %s\n" "$DEST"
printf "State file: %s\n" "$STATE_FILE"
