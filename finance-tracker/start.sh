#!/usr/bin/env bash
# Start the Finance Tracker app (backend + frontend).
# Usage: ./start.sh          — start both
#        ./start.sh stop     — kill both
#        ./start.sh restart  — stop then start

set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$DIR/backend"
FRONTEND_DIR="$DIR/frontend"
BACKEND_LOG="/tmp/finance-backend.out"
FRONTEND_LOG="/tmp/finance-frontend.out"

stop() {
  echo "Stopping..."
  pkill -f "uvicorn main:app" 2>/dev/null || true
  pkill -f "vite.*finance-tracker" 2>/dev/null || true
  lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
  lsof -ti:5175 2>/dev/null | xargs kill -9 2>/dev/null || true
  sleep 1
  echo "Stopped."
}

start() {
  if [ ! -f "$BACKEND_DIR/venv/bin/uvicorn" ]; then
    echo "Creating venv..."
    python3 -m venv "$BACKEND_DIR/venv"
    "$BACKEND_DIR/venv/bin/pip" install -q -r "$BACKEND_DIR/requirements.txt"
  fi

  if [ ! -f "$BACKEND_DIR/.env" ]; then
    echo "Note: backend/.env not found — copy backend/.env.example and fill in PLAID_CLIENT_ID/PLAID_SECRET."
  fi

  if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo "Installing frontend dependencies..."
    (cd "$FRONTEND_DIR" && npm install)
  fi

  echo "Starting backend (http://localhost:8000)..."
  cd "$BACKEND_DIR"
  ./venv/bin/uvicorn main:app --reload > "$BACKEND_LOG" 2>&1 &
  BACKEND_PID=$!

  echo "Starting frontend (http://localhost:5175)..."
  cd "$FRONTEND_DIR"
  npm run dev > "$FRONTEND_LOG" 2>&1 &
  FRONTEND_PID=$!

  for i in $(seq 1 15); do
    if curl -s http://localhost:8000/status > /dev/null 2>&1; then
      break
    fi
    sleep 1
  done

  if curl -s http://localhost:8000/status > /dev/null 2>&1; then
    echo "Backend ready (pid $BACKEND_PID)"
  else
    echo "Warning: backend may not be ready yet — check $BACKEND_LOG"
  fi
  echo "Frontend running (pid $FRONTEND_PID)"
  echo ""
  echo "Logs:"
  echo "  Backend:  tail -f $BACKEND_LOG"
  echo "  Frontend: tail -f $FRONTEND_LOG"
  echo ""
  echo "Open http://localhost:5175"
  echo "Stop with: $0 stop"
}

case "${1:-start}" in
  stop)    stop ;;
  restart) stop; start ;;
  start)   stop; start ;;
  *)       echo "Usage: $0 [start|stop|restart]"; exit 1 ;;
esac
