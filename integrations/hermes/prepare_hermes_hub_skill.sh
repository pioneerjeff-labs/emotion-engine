#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)

OUTPUT_ROOT="$REPO_ROOT/dist/hermes-hub"
PACKAGE="$OUTPUT_ROOT/emotion-engine"

case "$PACKAGE" in
  "$REPO_ROOT"/dist/hermes-hub/emotion-engine) ;;
  *)
    printf "Refusing to overwrite unexpected output path: %s\n" "$PACKAGE" >&2
    exit 1
    ;;
esac

rm -rf "$PACKAGE"
mkdir -p "$PACKAGE/scripts"

cp "$SCRIPT_DIR/emotion-engine/SKILL.md" "$PACKAGE/"
cp "$SCRIPT_DIR/emotion-engine/README.md" "$PACKAGE/"
cp "$SCRIPT_DIR/emotion-engine/install.sh" "$PACKAGE/"
cp "$SCRIPT_DIR/emotion-engine/scripts/hermes_emotion.sh" "$PACKAGE/scripts/"
cp "$REPO_ROOT/scripts/emotion_engine_utils.py" "$PACKAGE/scripts/"
cp "$REPO_ROOT/emotion-state-template.json" "$PACKAGE/"
cp "$REPO_ROOT/LICENSE" "$PACKAGE/"

chmod +x "$PACKAGE/install.sh" "$PACKAGE/scripts/hermes_emotion.sh"

printf "Prepared HermesHub skill directory:\n"
printf "  %s\n\n" "$PACKAGE"
printf "Publish from a machine with Hermes Agent installed:\n"
printf "  hermes skills publish %s --to github --repo pioneerjeff-labs/emotion-engine\n" "$PACKAGE"
