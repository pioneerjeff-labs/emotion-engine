#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ENGINE="$SCRIPT_DIR/emotion_engine_utils.py"
PYTHON=${PYTHON:-python3}

if [ "$#" -lt 1 ]; then
  COMMAND=status
else
  COMMAND=$1
  shift
fi

if [ -n "${CLAUDE_EMOTION_STATE:-}" ]; then
  STATE_FILE=$CLAUDE_EMOTION_STATE
elif [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then
  STATE_FILE="$CLAUDE_PROJECT_DIR/.emotion-engine/emotion-state.json"
elif [ -d "$PWD/.git" ] || [ -d "$PWD/.claude" ]; then
  STATE_FILE="$PWD/.emotion-engine/emotion-state.json"
else
  STATE_FILE="$HOME/.claude/emotion-engine/emotion-state.json"
fi

STATE_DIR=$(dirname -- "$STATE_FILE")
mkdir -p "$STATE_DIR"

if [ "$COMMAND" = "init" ]; then
  exec "$PYTHON" "$ENGINE" init "$STATE_FILE" "$@"
fi

if [ ! -f "$STATE_FILE" ]; then
  "$PYTHON" "$ENGINE" init "$STATE_FILE" >/dev/null
fi

exec "$PYTHON" "$ENGINE" "$COMMAND" "$STATE_FILE" "$@"
