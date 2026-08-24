#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
SOURCE="$REPO_ROOT/skills/emotion-engine"

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

printf "Prepared HermesHub skill directory:\n"
printf "  %s\n\n" "$PACKAGE"
printf "Publish from a machine with Hermes Agent installed:\n"
printf "  hermes skills publish %s --to github --repo pioneerjeff-labs/emotion-engine\n" "$PACKAGE"
