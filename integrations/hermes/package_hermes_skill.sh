#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
SOURCE="$REPO_ROOT/skills/emotion-engine"

OUTPUT="emotion-engine-hermes-skill.zip"
PYTHON=${PYTHON:-python3}
STAGE=$(mktemp -d "${TMPDIR:-/tmp}/emotion-engine-hermes.XXXXXX")
PACKAGE="$STAGE/emotion-engine"
trap 'rm -rf "$STAGE"' EXIT

rm -f "$SCRIPT_DIR/$OUTPUT"
mkdir -p "$PACKAGE/scripts" "$PACKAGE/spec"

cp "$SOURCE/SKILL.md" "$PACKAGE/"
cp "$SOURCE/README.md" "$PACKAGE/"
cp "$SOURCE/install.sh" "$PACKAGE/"
cp "$SOURCE/scripts/hermes_emotion.sh" "$PACKAGE/scripts/"
cp "$SOURCE/scripts/emotion_engine_utils.py" "$PACKAGE/scripts/"
cp "$SOURCE/emotion-state-template.json" "$PACKAGE/"
cp "$SOURCE/spec/emotion-state.schema.json" "$PACKAGE/spec/"
cp "$SOURCE/LICENSE" "$PACKAGE/"
chmod +x "$PACKAGE/install.sh" "$PACKAGE/scripts/hermes_emotion.sh"

(cd "$STAGE" && "$PYTHON" -m zipfile -c "$SCRIPT_DIR/$OUTPUT" emotion-engine)
printf "Created %s\n" "$SCRIPT_DIR/$OUTPUT"
