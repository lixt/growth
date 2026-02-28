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

"$BACKEND_VENV" app.main:app --host 0.0.0.0 --port 8000 &
BACK_PID=$!

cd "$ROOT_DIR/streamlit"
"$STREAMLIT_BIN" run app.py --server.port 8501 --server.address 0.0.0.0 &
FRONT_PID=$!

cleanup() {
  kill $BACK_PID $FRONT_PID 2>/dev/null || true
}
trap cleanup EXIT

wait -n
