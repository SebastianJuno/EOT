#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

make package-macos

SRC_APP="dist/EOT Diff Tool.app"
DEST_DIR="local-app"
DEST_APP="$DEST_DIR/EOT Diff Tool.app"

rm -rf "$DEST_APP"
cp -R "$SRC_APP" "$DEST_APP"

echo "Local app installed at: $DEST_APP"
echo "You can double-click it from Finder."
