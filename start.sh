#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo "============================================"
echo "  AI Video Workflow - Starting..."
echo "============================================"

command -v python3 >/dev/null || { echo "[ERROR] python3 not found"; exit 1; }
command -v node >/dev/null    || { echo "[ERROR] node not found"; exit 1; }
command -v npm >/dev/null     || { echo "[ERROR] npm not found"; exit 1; }

if ! command -v ffmpeg >/dev/null; then
  if [ -x "tools/ffmpeg/ffmpeg" ]; then
    echo "[INFO] Using bundled FFmpeg in tools/ffmpeg"
  else
    echo "[WARN] FFmpeg not found. Video processing nodes will fail."
  fi
fi

if [ ! -f "backend/.venv/bin/python" ]; then
  echo "[SETUP] Creating Python virtual environment..."
  python3 -m venv backend/.venv
fi
if [ ! -f "backend/.venv/.deps_installed" ]; then
  echo "[SETUP] Installing backend dependencies..."
  backend/.venv/bin/pip install -r backend/requirements.txt
  touch backend/.venv/.deps_installed
fi

if [ ! -d "frontend/node_modules" ]; then
  echo "[SETUP] Installing frontend dependencies..."
  (cd frontend && npm install)
fi

[ -f "backend/.env" ] || cp .env.example backend/.env 2>/dev/null || true

echo "[START] Backend  -> http://localhost:8000"
(cd backend && .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000) &
BACKEND_PID=$!
sleep 2
echo "[START] Frontend -> http://localhost:5173"
(cd frontend && npm run dev) &
FRONTEND_PID=$!

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
sleep 4
(command -v xdg-open >/dev/null && xdg-open http://localhost:5173) || true
wait
