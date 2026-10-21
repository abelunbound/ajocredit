#!/usr/bin/env bash
# Local-only launcher: FastAPI (8000) + Dash (8055).
# Not a production process manager. Ctrl+C stops both children.

# Find bash via PATH so this works on macOS/Linux without a hardcoded /bin/bash.
# set -e: exit if a command fails (e.g. missing venv, alembic error).
# set -u: exit if an unset variable is used.
# set -o pipefail: a pipeline fails if any stage fails, not only the last.
set -euo pipefail

# $0 is this script. dirname is utils/. .. is the repo root.
# cd+pwd makes ROOT an absolute path so the script works from any cwd.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Activate the project venv so python/alembic/uvicorn resolve consistently.
# SC1091: shellcheck cannot follow the generated activate script; that is expected.
# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"

# Apply schema to DATABASE_URL (local SQLite from .env). Safe to re-run.
# Must finish before uvicorn starts so the API does not boot against an empty file.
"$ROOT/.venv/bin/python" -m alembic upgrade head

# FastAPI in the background. --reload is for local file watching.
# --no-proxy-headers: do not trust X-Forwarded-For (required by auth rate limits).
# $! is the PID of that background job. Capture it so cleanup can kill it.
"$ROOT/.venv/bin/python" -m uvicorn api:app --reload --no-proxy-headers &
API_PID=$!

# Dash UI in the background. Loads .env itself; defaults AJO_API_BASE to :8000.
"$ROOT/.venv/bin/python" app_dash_web.py &
UI_PID=$!

# Stop both children when this script exits or gets INT/TERM (Ctrl+C).
# 2>/dev/null || true: ignore "already dead" so the trap never fails the script.
cleanup() {
  kill "$API_PID" "$UI_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Block until a child exits. Without this the script would return immediately
# and the trap would kill the servers.
wait
