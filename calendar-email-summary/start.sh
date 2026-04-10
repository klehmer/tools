#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"

# Install dependencies if needed
if [ ! -d "$BACKEND_DIR/.venv" ]; then
  echo "Creating backend virtual environment..."
  python3 -m venv "$BACKEND_DIR/.venv"
fi

if ! "$BACKEND_DIR/.venv/bin/pip" show fastapi &>/dev/null; then
  echo "Installing backend dependencies..."
  "$BACKEND_DIR/.venv/bin/pip" install -r "$BACKEND_DIR/requirements.txt"
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "Installing frontend dependencies..."
  (cd "$FRONTEND_DIR" && npm install)
fi

cleanup() {
  echo "Shutting down..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
}
trap cleanup EXIT INT TERM

# Start backend (port 8001)
echo "Starting backend on http://localhost:8001 ..."
"$BACKEND_DIR/.venv/bin/uvicorn" main:app --reload --port 8001 --app-dir "$BACKEND_DIR" &
BACKEND_PID=$!

# Start frontend (port 5174)
echo "Starting frontend on http://localhost:5174 ..."
(cd "$FRONTEND_DIR" && npx vite) &
FRONTEND_PID=$!

echo "Ready — open http://localhost:5174"
wait
