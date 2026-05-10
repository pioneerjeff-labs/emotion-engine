#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ENGINE="$SCRIPT_DIR/emotion_engine_utils.py"
PYTHON=${PYTHON:-python3}

if [ ! -f "$ENGINE" ]; then
  PACKAGE_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
  REPO_ROOT=$(CDPATH= cd -- "$PACKAGE_DIR/../../.." && pwd)
  ENGINE="$REPO_ROOT/scripts/emotion_engine_utils.py"
fi

if [ ! -f "$ENGINE" ]; then
  printf "Emotion Engine core not found. Expected scripts/emotion_engine_utils.py.\n" >&2
  exit 1
fi

if [ "$#" -lt 1 ]; then
  COMMAND=status
else
  COMMAND=$1
  shift
fi

if [ -n "${HERMES_EMOTION_STATE:-}" ]; then
  STATE_FILE=$HERMES_EMOTION_STATE
elif [ -n "${HERMES_PROJECT_DIR:-}" ]; then
  STATE_FILE="$HERMES_PROJECT_DIR/.emotion-engine/hermes-state.json"
elif [ -d "$PWD/.git" ] || [ -d "$PWD/.hermes" ]; then
  STATE_FILE="$PWD/.emotion-engine/hermes-state.json"
else
  STATE_FILE="$HOME/.hermes/emotion-engine/emotion-state.json"
fi

STATE_DIR=$(dirname -- "$STATE_FILE")
mkdir -p "$STATE_DIR"

if [ "$COMMAND" = "init" ]; then
  exec "$PYTHON" "$ENGINE" init "$STATE_FILE" "$@"
fi

if [ ! -s "$STATE_FILE" ]; then
  "$PYTHON" "$ENGINE" init "$STATE_FILE" >/dev/null
fi

exec "$PYTHON" "$ENGINE" "$COMMAND" "$STATE_FILE" "$@"
