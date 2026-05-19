#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)

OUTPUT="emotion-engine-hermes-skill.zip"
PYTHON=${PYTHON:-python3}
STAGE=$(mktemp -d "${TMPDIR:-/tmp}/emotion-engine-hermes.XXXXXX")
PACKAGE="$STAGE/emotion-engine"
trap 'rm -rf "$STAGE"' EXIT

rm -f "$SCRIPT_DIR/$OUTPUT"
mkdir -p "$PACKAGE/scripts"

cp "$SCRIPT_DIR/emotion-engine/SKILL.md" "$PACKAGE/"
cp "$SCRIPT_DIR/emotion-engine/README.md" "$PACKAGE/"
cp "$REPO_ROOT/scripts/emotion_engine_utils.py" "$PACKAGE/scripts/"
cp "$REPO_ROOT/emotion-state-template.json" "$PACKAGE/"
cp "$REPO_ROOT/LICENSE" "$PACKAGE/"

cat > "$PACKAGE/install.sh" <<'SH'
#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SKILLS_DIR=${HERMES_SKILLS_DIR:-"$HOME/.hermes/skills"}
DEST=${HERMES_SKILL_DEST:-"$SKILLS_DIR/personal/emotion-engine"}
STATE_FILE=${HERMES_EMOTION_STATE:-"$HOME/.hermes/emotion-engine/emotion-state.json"}
PYTHON=${PYTHON:-python3}

CORE_SCRIPT="$SCRIPT_DIR/scripts/emotion_engine_utils.py"
STATE_TEMPLATE="$SCRIPT_DIR/emotion-state-template.json"

if [ ! -f "$CORE_SCRIPT" ]; then
  printf "Emotion Engine core not found in package: %s\n" "$CORE_SCRIPT" >&2
  exit 1
fi
if [ ! -f "$STATE_TEMPLATE" ]; then
  printf "Emotion Engine state template not found in package: %s\n" "$STATE_TEMPLATE" >&2
  exit 1
fi

mkdir -p "$DEST/scripts"
mkdir -p "$(dirname -- "$STATE_FILE")"

if [ "$SCRIPT_DIR" != "$DEST" ]; then
  cp "$SCRIPT_DIR/SKILL.md" "$DEST/"
  cp "$SCRIPT_DIR/README.md" "$DEST/"
  cp "$SCRIPT_DIR/install.sh" "$DEST/"
  cp "$SCRIPT_DIR/scripts/hermes_emotion.sh" "$DEST/scripts/"
  cp "$CORE_SCRIPT" "$DEST/scripts/emotion_engine_utils.py"
  cp "$STATE_TEMPLATE" "$DEST/emotion-state-template.json"
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
SH

cat > "$PACKAGE/scripts/hermes_emotion.sh" <<'SH'
#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ENGINE="$SCRIPT_DIR/emotion_engine_utils.py"
PYTHON=${PYTHON:-python3}

if [ ! -f "$ENGINE" ]; then
  printf "Emotion Engine core not found in package: %s\n" "$ENGINE" >&2
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
SH

(cd "$STAGE" && "$PYTHON" -m zipfile -c "$SCRIPT_DIR/$OUTPUT" emotion-engine)
printf "Created %s\n" "$SCRIPT_DIR/$OUTPUT"
