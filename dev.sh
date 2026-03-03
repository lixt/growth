#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

BACKEND_VENV="$ROOT_DIR/backend/.venv/bin/uvicorn"
STREAMLIT_BIN="$ROOT_DIR/backend/.venv/bin/streamlit"

if [[ ! -x "$BACKEND_VENV" ]]; then
  echo "Backend venv not found. Create it first in $ROOT_DIR/backend/.venv" >&2
  exit 1
fi

if [[ ! -x "$STREAMLIT_BIN" ]]; then
  echo "Streamlit not found in backend venv. Install it or use streamlit/requirements.txt" >&2
  exit 1
fi

"$BACKEND_VENV" app.main:app \
  --app-dir "$ROOT_DIR/backend" \
  --reload \
  --reload-dir "$ROOT_DIR/backend/app" \
  --host 0.0.0.0 \
  --port 8000 &
BACK_PID=$!

cd "$ROOT_DIR/streamlit"
"$STREAMLIT_BIN" run app.py --server.port 8501 --server.address 0.0.0.0 &
FRONT_PID=$!

cleanup() {
  kill $BACK_PID $FRONT_PID 2>/dev/null || true
}
trap cleanup EXIT

# Bash 3 (macOS default) does not support `wait -n`.
# Poll until either child exits, then trigger cleanup via trap.
while true; do
  if ! kill -0 "$BACK_PID" 2>/dev/null; then
    wait "$BACK_PID" || true
    break
  fi
  if ! kill -0 "$FRONT_PID" 2>/dev/null; then
    wait "$FRONT_PID" || true
    break
  fi
  sleep 1
done
