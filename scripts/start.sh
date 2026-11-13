#!/usr/bin/env sh
# Run NomadGrid without Docker (macOS / Linux / git-bash):  sh scripts/start.sh
# Creates a virtualenv, installs the backend, builds the UI if Node.js is available, starts everything.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null 2>&1 || PY=python
command -v "$PY" >/dev/null 2>&1 || { echo "Python 3.10+ is required (or use: docker compose up --build)"; exit 1; }

cd "$ROOT/backend"
[ -d .venv ] || "$PY" -m venv .venv
if [ -x .venv/bin/python ]; then VPY=.venv/bin/python; else VPY=.venv/Scripts/python.exe; fi
"$VPY" -m pip install -q -r requirements.txt

if [ ! -f "$ROOT/frontend/dist/index.html" ]; then
  if command -v npm >/dev/null 2>&1; then
    echo "Building the web UI (first run only)..."
    (cd "$ROOT/frontend" && { npm ci || npm install; } && npm run build) || echo "UI build failed - continuing with the API only."
  else
    echo "Node.js not found - starting the API only. Install Node 20+ and re-run to get the web UI."
  fi
fi

exec "$VPY" -m app
