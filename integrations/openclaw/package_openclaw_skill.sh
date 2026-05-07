#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

OUTPUT="emotion-engine-openclaw-skill.zip"
PYTHON=${PYTHON:-python3}
rm -f "$OUTPUT"

"$PYTHON" -m zipfile -c "$OUTPUT" emotion-engine
printf "Created %s\n" "$SCRIPT_DIR/$OUTPUT"
