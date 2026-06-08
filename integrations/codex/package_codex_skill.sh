#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)

OUTPUT="emotion-engine-codex-skill.zip"
PYTHON=${PYTHON:-python3}
STAGE=$(mktemp -d "${TMPDIR:-/tmp}/emotion-engine-codex.XXXXXX")
PACKAGE="$STAGE/emotion-engine-codex"
trap 'rm -rf "$STAGE"' EXIT

rm -f "$SCRIPT_DIR/$OUTPUT"
mkdir -p "$PACKAGE/scripts" "$PACKAGE/spec"

cp "$SCRIPT_DIR/emotion-engine-codex/SKILL.md" "$PACKAGE/"
cp "$SCRIPT_DIR/emotion-engine-codex/README.md" "$PACKAGE/"
cp "$SCRIPT_DIR/emotion-engine-codex/install.sh" "$PACKAGE/"
cp "$SCRIPT_DIR/emotion-engine-codex/scripts/codex_emotion.sh" "$PACKAGE/scripts/"
cp "$SCRIPT_DIR/emotion-engine-codex/scripts/nora_demo.py" "$PACKAGE/scripts/"
cp "$REPO_ROOT/scripts/emotion_engine_utils.py" "$PACKAGE/scripts/"
cp "$REPO_ROOT/emotion-state-template.json" "$PACKAGE/"
cp "$REPO_ROOT/spec/emotion-state.schema.json" "$PACKAGE/spec/"
cp "$REPO_ROOT/LICENSE" "$PACKAGE/"

(cd "$STAGE" && "$PYTHON" -m zipfile -c "$SCRIPT_DIR/$OUTPUT" emotion-engine-codex)
printf "Created %s\n" "$SCRIPT_DIR/$OUTPUT"
