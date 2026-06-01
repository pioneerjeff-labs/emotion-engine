#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../../.." && pwd)
WORKSPACE=${OPENCLAW_WORKSPACE:-"$HOME/.openclaw/workspace"}

if [ -t 0 ]; then
  printf "OpenClaw workspace [%s]: " "$WORKSPACE"
  read -r INPUT_WORKSPACE || true
  if [ "${INPUT_WORKSPACE:-}" ]; then
    WORKSPACE=$INPUT_WORKSPACE
  fi
fi

SKILLS_DIR="$WORKSPACE/skills"
DEST="$SKILLS_DIR/emotion-engine"
STATE_FILE="$WORKSPACE/emotion-state.json"
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

if [ "$SCRIPT_DIR" != "$DEST" ]; then
  mkdir -p "$DEST/scripts" "$DEST/spec"
  cp "$SCRIPT_DIR/SKILL.md" "$DEST/"
  cp "$SCRIPT_DIR/README.md" "$DEST/"
  cp "$SCRIPT_DIR/install.sh" "$DEST/"
  cp "$CORE_SCRIPT" "$DEST/scripts/emotion_engine_utils.py"
  cp "$STATE_TEMPLATE" "$DEST/emotion-state-template.json"
  if [ -f "$SCHEMA_FILE" ]; then
    cp "$SCHEMA_FILE" "$DEST/spec/emotion-state.schema.json"
  fi
  if [ -f "$LICENSE_FILE" ]; then
    cp "$LICENSE_FILE" "$DEST/"
  fi
fi

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
    "$PYTHON" "$DEST/scripts/emotion_engine_utils.py" configure "$STATE_FILE" --style "$STYLE"
  else
    "$PYTHON" "$DEST/scripts/emotion_engine_utils.py" status "$STATE_FILE"
  fi
else
  "$PYTHON" "$DEST/scripts/emotion_engine_utils.py" status "$STATE_FILE"
fi

printf "\nEmotion Engine is installed.\n"
printf "You can later tune it in chat, or run:\n"
printf "  python3 %s/scripts/emotion_engine_utils.py tune %s \"make it warmer\"\n" "$DEST" "$STATE_FILE"
