#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log() {
  printf "\n[bootstrap] %s\n" "$1"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "ERROR: required command '$1' not found" >&2
    exit 1
  }
}

log "Checking Xcode Command Line Tools"
if ! xcode-select -p >/dev/null 2>&1; then
  echo "Xcode Command Line Tools are required."
  echo "Running: xcode-select --install"
  xcode-select --install || true
  echo "Complete the install dialog, then rerun this script."
  exit 1
fi

if ! command -v brew >/dev/null 2>&1; then
  log "Homebrew not found. Installing Homebrew"
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

if [ -x /opt/homebrew/bin/brew ]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
elif [ -x /usr/local/bin/brew ]; then
  eval "$(/usr/local/bin/brew shellenv)"
fi

require_cmd brew

log "Installing dependencies (python@3.12, openjdk@17, maven)"
brew install python@3.12 openjdk@17 maven

if ! command -v python3.12 >/dev/null 2>&1; then
  echo "python3.12 still not found on PATH."
  echo "Run one of the following then restart terminal:"
  echo "  eval \"\$($(brew --prefix)/bin/brew shellenv)\""
  exit 1
fi

log "Python version"
python3.12 --version

log "Project setup"
cd "$ROOT_DIR"
make setup
make build-parser

log "Bootstrap complete"
echo "Desktop dev run:"
echo "  cd '$ROOT_DIR' && make run-desktop-dev"
echo "Desktop package build:"
echo "  cd '$ROOT_DIR' && make package-macos"
