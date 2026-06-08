#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ENGINE="$SCRIPT_DIR/emotion_engine_utils.py"
NORA_DEMO="$SCRIPT_DIR/nora_demo.py"
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

if [ ! -f "$NORA_DEMO" ]; then
  PACKAGE_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
  REPO_ROOT=$(CDPATH= cd -- "$PACKAGE_DIR/../../.." && pwd)
  NORA_DEMO="$REPO_ROOT/integrations/codex/emotion-engine-codex/scripts/nora_demo.py"
fi

if [ "$#" -lt 1 ]; then
  COMMAND=status
else
  COMMAND=$1
  shift
fi

if [ -n "${CODEX_EMOTION_STATE:-}" ]; then
  STATE_FILE=$CODEX_EMOTION_STATE
elif [ -n "${CODEX_PROJECT_DIR:-}" ]; then
  STATE_FILE="$CODEX_PROJECT_DIR/.emotion-engine/codex-state.json"
elif [ -d "$PWD/.git" ] || [ -d "$PWD/.codex" ]; then
  STATE_FILE="$PWD/.emotion-engine/codex-state.json"
elif [ -d "$HOME/.codex" ]; then
  STATE_FILE="$HOME/.codex/emotion-engine/emotion-state.json"
elif [ -d "$HOME/.agents" ]; then
  STATE_FILE="$HOME/.agents/emotion-engine/emotion-state.json"
else
  STATE_FILE="$HOME/.codex/emotion-engine/emotion-state.json"
fi

STATE_DIR=$(dirname -- "$STATE_FILE")
mkdir -p "$STATE_DIR"

if [ "$COMMAND" = "where" ]; then
  printf "%s\n" "$STATE_FILE"
  exit 0
fi

if [ "$COMMAND" = "nora-demo" ]; then
  if [ ! -f "$NORA_DEMO" ]; then
    printf "Nora demo script not found.\n" >&2
    exit 1
  fi
  exec "$PYTHON" "$NORA_DEMO" --engine "$ENGINE" "$@"
fi

if [ "$COMMAND" = "init" ]; then
  exec "$PYTHON" "$ENGINE" init "$STATE_FILE" "$@"
fi

if [ ! -s "$STATE_FILE" ]; then
  "$PYTHON" "$ENGINE" init "$STATE_FILE" >/dev/null
fi

exec "$PYTHON" "$ENGINE" "$COMMAND" "$STATE_FILE" "$@"
