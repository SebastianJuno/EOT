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

# Requires a universal2 Python environment for true universal output.
pyinstaller --noconfirm --clean --target-arch universal2 desktop/pyinstaller.spec

APP_PATH="dist/EOT Diff Tool.app"
if [[ ! -d "$APP_PATH" ]]; then
  echo "ERROR: App bundle not created at $APP_PATH"
  exit 1
fi

ZIP_PATH="dist/EOT-Diff-Tool-mac-universal.zip"
rm -f "$ZIP_PATH"
# Preserve app metadata/resource forks for mac app distribution.
ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$ZIP_PATH"

echo "Build complete: $ZIP_PATH"
echo "Distribution note: this is unsigned (internal testing)."
echo "On first launch, users may need right-click -> Open."
