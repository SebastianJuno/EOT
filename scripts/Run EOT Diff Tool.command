#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -x ".venv/bin/python" ]; then
  osascript -e 'display dialog "App environment missing. Running bootstrap first." buttons {"OK"} default button "OK"'
  make -f scripts/Makefile bootstrap-macos
fi

# Prefer root app entry if available.
if [ -d "EOT Diff Tool.app" ]; then
  open "EOT Diff Tool.app"
  exit 0
fi

# Fallback to desktop dev launcher.
make -f scripts/Makefile run-desktop-dev
