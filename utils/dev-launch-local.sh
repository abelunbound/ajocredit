#!/usr/bin/env bash
# Local-only launcher: FastAPI (8000) + Dash (8055).
# Not a production process manager. One command. Ctrl+C stops both.
#
# Run from anywhere:
#   ./utils/dev-launch-local.sh
# The script cds to the repo root, so .env and local/ paths resolve there.

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
# alembic's env.py loads .env from the repo root when the variables are unset.
"$ROOT/.venv/bin/python" -m alembic upgrade head

# Each background command gets its own process group. Ctrl+C is delivered to
# this script, not swallowed by Dash or by uvicorn's reloader. The trap then
# signals both groups, which also covers child workers.
set -m

# FastAPI on port 8000 (uvicorn's default). --reload is for local file watching.
# --no-proxy-headers: do not trust X-Forwarded-For (required by auth rate limits).
# backend.api loads .env unless this is a pytest process.
"$ROOT/.venv/bin/python" -m uvicorn backend.api:app --reload --no-proxy-headers &
API_PID=$!

# Dash on port 8055 (DASH_PORT, default 8055). The UI loads .env and, when
# AJO_API_BASE is empty, sets it to http://127.0.0.1:8000.
# The argv path contains app_dash_web.py so `pkill -f app_dash_web.py` still matches.
"$ROOT/.venv/bin/python" "$ROOT/frontend/app_dash_web.py" &
UI_PID=$!

STOPPED=0

# Signal both process groups. Idempotent: EXIT and INT can both fire.
cleanup() {
  if [[ "$STOPPED" -eq 1 ]]; then
    return
  fi
  STOPPED=1
  # `-- -PID` is the process group. TERM first, then KILL if either is still up.
  kill -TERM -- "-${API_PID}" "-${UI_PID}" 2>/dev/null || true
  local _i
  for _i in 1 2 3 4 5 6 7 8 9 10; do
    if ! kill -0 "$API_PID" 2>/dev/null && ! kill -0 "$UI_PID" 2>/dev/null; then
      break
    fi
    sleep 0.1
  done
  kill -KILL -- "-${API_PID}" "-${UI_PID}" 2>/dev/null || true
  wait "$API_PID" "$UI_PID" 2>/dev/null || true
}

# bash runs this trap as soon as a trapped signal interrupts `wait`.
# Without that, a Dash process that ignores SIGINT keeps `wait` blocked and
# the trap never runs, so the UI survives Ctrl+C.
on_signal() {
  cleanup
  exit 130
}
trap on_signal INT TERM
trap cleanup EXIT

# Block until both children have exited. A signal interrupts this wait.
wait "$API_PID" "$UI_PID" || true
