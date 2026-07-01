#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../../.." && pwd)
if [ -n "${CODEX_SKILLS_DIR:-}" ]; then
  SKILLS_DIR=$CODEX_SKILLS_DIR
elif [ -d "$HOME/.codex/skills" ]; then
  SKILLS_DIR="$HOME/.codex/skills"
else
  SKILLS_DIR="$HOME/.agents/skills"
fi
DEST="$SKILLS_DIR/emotion-engine-codex"
if [ -n "${CODEX_EMOTION_STATE:-}" ]; then
  STATE_FILE=$CODEX_EMOTION_STATE
else
  case $SKILLS_DIR in
    "$HOME/.agents/skills"|"$HOME/.agents/skills/"*)
      STATE_FILE="$HOME/.agents/emotion-engine/emotion-state.json"
      ;;
    *)
      STATE_FILE="$HOME/.codex/emotion-engine/emotion-state.json"
      ;;
  esac
fi
PYTHON=${PYTHON:-python3}

CORE_SCRIPT="$SCRIPT_DIR/scripts/emotion_engine_utils.py"
MCP_SCRIPT="$SCRIPT_DIR/scripts/emotion_engine_mcp.py"
REGISTER_SCRIPT="$SCRIPT_DIR/scripts/register_mcp_client.py"
STATE_TEMPLATE="$SCRIPT_DIR/emotion-state-template.json"
SCHEMA_FILE="$SCRIPT_DIR/spec/emotion-state.schema.json"
LICENSE_FILE="$SCRIPT_DIR/LICENSE"

if [ ! -f "$CORE_SCRIPT" ]; then
  CORE_SCRIPT="$REPO_ROOT/scripts/emotion_engine_utils.py"
fi
if [ ! -f "$MCP_SCRIPT" ]; then
  MCP_SCRIPT="$REPO_ROOT/scripts/emotion_engine_mcp.py"
fi
if [ ! -f "$REGISTER_SCRIPT" ]; then
  REGISTER_SCRIPT="$REPO_ROOT/scripts/register_mcp_client.py"
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
  cp "$SCRIPT_DIR/scripts/codex_emotion.sh" "$DEST/scripts/"
  cp "$SCRIPT_DIR/scripts/nora_demo.py" "$DEST/scripts/"
  cp "$CORE_SCRIPT" "$DEST/scripts/emotion_engine_utils.py"
  if [ -f "$MCP_SCRIPT" ]; then
    cp "$MCP_SCRIPT" "$DEST/scripts/emotion_engine_mcp.py"
  fi
  if [ -f "$REGISTER_SCRIPT" ]; then
    cp "$REGISTER_SCRIPT" "$DEST/scripts/register_mcp_client.py"
  fi
  cp "$STATE_TEMPLATE" "$DEST/emotion-state-template.json"
  if [ -f "$SCHEMA_FILE" ]; then
    cp "$SCHEMA_FILE" "$DEST/spec/emotion-state.schema.json"
  fi
  if [ -f "$LICENSE_FILE" ]; then
    cp "$LICENSE_FILE" "$DEST/"
  fi
fi

chmod +x "$DEST/scripts/codex_emotion.sh" "$DEST/install.sh"
if [ -f "$DEST/scripts/emotion_engine_mcp.py" ]; then
  chmod +x "$DEST/scripts/emotion_engine_mcp.py"
fi
if [ -f "$DEST/scripts/register_mcp_client.py" ]; then
  chmod +x "$DEST/scripts/register_mcp_client.py"
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
    CODEX_EMOTION_STATE="$STATE_FILE" "$DEST/scripts/codex_emotion.sh" configure --style "$STYLE"
  else
    CODEX_EMOTION_STATE="$STATE_FILE" "$DEST/scripts/codex_emotion.sh" status
  fi
else
  CODEX_EMOTION_STATE="$STATE_FILE" "$DEST/scripts/codex_emotion.sh" status
fi

printf "\nCodex Skill installed at: %s\n" "$DEST"
printf "State file: %s\n" "$STATE_FILE"
