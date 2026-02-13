#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -x ".venv/bin/python" ]; then
  echo "ERROR: .venv not found. Run 'make -f scripts/Makefile setup' first."
  exit 1
fi

URL="http://127.0.0.1:8000"
HEALTH_URL="$URL/health"

# Start server in background from the project venv.
. .venv/bin/activate
uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000 &
SERVER_PID=$!

cleanup() {
  if kill -0 "$SERVER_PID" >/dev/null 2>&1; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

# Wait up to ~20 seconds for health endpoint.
for _ in $(seq 1 40); do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

if ! curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
  echo "ERROR: Server failed to start at $HEALTH_URL"
  exit 1
fi

open "$URL"

echo "Server running at $URL (Press Ctrl+C to stop)"
wait "$SERVER_PID"
