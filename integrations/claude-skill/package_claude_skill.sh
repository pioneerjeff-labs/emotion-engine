#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)

OUTPUT="emotion-engine-claude-skill.zip"
PYTHON=${PYTHON:-python3}
STAGE=$(mktemp -d "${TMPDIR:-/tmp}/emotion-engine-claude.XXXXXX")
PACKAGE="$STAGE/emotion-engine"
trap 'rm -rf "$STAGE"' EXIT

rm -f "$SCRIPT_DIR/$OUTPUT"
mkdir -p "$PACKAGE/scripts" "$PACKAGE/spec"

cp "$SCRIPT_DIR/emotion-engine/SKILL.md" "$PACKAGE/"
cp "$SCRIPT_DIR/emotion-engine/README.md" "$PACKAGE/"
cp "$SCRIPT_DIR/emotion-engine/install.sh" "$PACKAGE/"
cp "$SCRIPT_DIR/emotion-engine/scripts/claude_emotion.sh" "$PACKAGE/scripts/"
cp "$REPO_ROOT/scripts/emotion_engine_utils.py" "$PACKAGE/scripts/"
cp "$REPO_ROOT/emotion-state-template.json" "$PACKAGE/"
cp "$REPO_ROOT/spec/emotion-state.schema.json" "$PACKAGE/spec/"
cp "$REPO_ROOT/LICENSE" "$PACKAGE/"

(cd "$STAGE" && "$PYTHON" -m zipfile -c "$SCRIPT_DIR/$OUTPUT" emotion-engine)
printf "Created %s\n" "$SCRIPT_DIR/$OUTPUT"
