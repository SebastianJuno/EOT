#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if [ ! -x ".venv/bin/python" ]; then
  osascript -e 'display dialog "App environment missing. Running bootstrap first." buttons {"OK"} default button "OK"'
  make bootstrap-macos
fi

# Prefer packaged local app if available.
if [ -d "local-app/EOT Diff Tool.app" ]; then
  open "local-app/EOT Diff Tool.app"
  exit 0
fi

# Fallback to desktop dev launcher.
make run-desktop-dev
