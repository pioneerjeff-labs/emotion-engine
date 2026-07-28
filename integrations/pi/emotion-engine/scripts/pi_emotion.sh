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

find_pi_project_root() {
  SEARCH_DIR=$PWD
  while :; do
    if [ -d "$SEARCH_DIR/.pi" ] || [ -e "$SEARCH_DIR/.git" ]; then
      printf "%s\n" "$SEARCH_DIR"
      return 0
    fi
    PARENT_DIR=$(dirname -- "$SEARCH_DIR")
    if [ "$PARENT_DIR" = "$SEARCH_DIR" ]; then
      return 1
    fi
    SEARCH_DIR=$PARENT_DIR
  done
}

if [ -n "${PI_EMOTION_STATE:-}" ]; then
  STATE_FILE=$PI_EMOTION_STATE
elif [ -n "${PI_PROJECT_DIR:-}" ]; then
  STATE_FILE="$PI_PROJECT_DIR/.emotion-engine/pi-state.json"
elif PI_PROJECT_ROOT=$(find_pi_project_root); then
  STATE_FILE="$PI_PROJECT_ROOT/.emotion-engine/pi-state.json"
else
  STATE_FILE="$HOME/.pi/agent/emotion-engine/emotion-state.json"
fi

STATE_DIR=$(dirname -- "$STATE_FILE")
mkdir -p "$STATE_DIR"

if [ "$COMMAND" = "where" ]; then
  printf "%s\n" "$STATE_FILE"
  exit 0
fi

if [ "$COMMAND" = "init" ]; then
  exec "$PYTHON" "$ENGINE" init "$STATE_FILE" "$@"
fi

if [ ! -s "$STATE_FILE" ]; then
  "$PYTHON" "$ENGINE" init "$STATE_FILE" >/dev/null
fi

exec "$PYTHON" "$ENGINE" "$COMMAND" "$STATE_FILE" "$@"
