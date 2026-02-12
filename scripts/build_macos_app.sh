#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "ERROR: macOS build only."
  exit 1
fi

if [[ ! -x .venv/bin/python ]]; then
  echo "ERROR: .venv missing. Run 'make setup' first."
  exit 1
fi

. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-desktop.txt

make build-parser

rm -rf build dist

# Build from spec. PyInstaller does not allow --target-arch with a .spec file.
pyinstaller --noconfirm --clean desktop/pyinstaller.spec

APP_PATH="dist/EOT Diff Tool.app"
if [[ ! -d "$APP_PATH" ]]; then
  echo "ERROR: App bundle not created at $APP_PATH"
  exit 1
fi

ARCH="$(uname -m)"
if [[ "$ARCH" == "arm64" ]]; then
  ZIP_PATH="dist/EOT-Diff-Tool-mac-arm64.zip"
elif [[ "$ARCH" == "x86_64" ]]; then
  ZIP_PATH="dist/EOT-Diff-Tool-mac-x64.zip"
else
  ZIP_PATH="dist/EOT-Diff-Tool-mac-${ARCH}.zip"
fi

rm -f "$ZIP_PATH" "dist/EOT-Diff-Tool-mac-universal.zip"
# Preserve app metadata/resource forks for mac app distribution.
ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$ZIP_PATH"

# Keep legacy name for compatibility with existing docs/workflows.
cp "$ZIP_PATH" "dist/EOT-Diff-Tool-mac-universal.zip"

echo "Build complete: $ZIP_PATH"
echo "Distribution note: this is unsigned (internal testing)."
echo "On first launch, users may need right-click -> Open."
