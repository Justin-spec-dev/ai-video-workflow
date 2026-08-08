@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo   AI Video Workflow - Starting...
echo ============================================

REM ---- Check Python ----
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.11+ and add it to PATH.
    pause & exit /b 1
)

REM ---- Check Node.js ----
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Please install Node.js 18+ and add it to PATH.
    pause & exit /b 1
)

REM ---- Check FFmpeg (env PATH, else bundled tools) ----
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    if exist "tools\ffmpeg\ffmpeg.exe" (
        echo [INFO] Using bundled FFmpeg in tools\ffmpeg
    ) else (
        echo [WARN] FFmpeg not found in PATH or tools\ffmpeg. Video processing nodes will fail.
        echo        Download FFmpeg and either add to PATH or place binaries in tools\ffmpeg\
    )
)

REM ---- Backend venv + deps ----
if not exist "backend\.venv\Scripts\python.exe" (
    echo [SETUP] Creating Python virtual environment...
    python -m venv backend\.venv
)
if not exist "backend\.venv\.deps_installed" (
    echo [SETUP] Installing backend dependencies...
    backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
    if errorlevel 1 ( echo [ERROR] pip install failed. & pause & exit /b 1 )
    echo done > backend\.venv\.deps_installed
)

REM ---- Frontend deps ----
if not exist "frontend\node_modules" (
    echo [SETUP] Installing frontend dependencies...
    pushd frontend
    call npm install
    if errorlevel 1 ( popd & echo [ERROR] npm install failed. & pause & exit /b 1 )
    popd
)

REM ---- .env ----
if not exist "backend\.env" (
    if exist ".env.example" copy ".env.example" "backend\.env" >nul
)

echo [START] Backend  -^> http://localhost:8000
echo [START] Frontend -^> http://localhost:5173

start "AVW-Backend" cmd /k "cd /d "%~dp0backend" && .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
timeout /t 3 /nobreak >nul
start "AVW-Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"
timeout /t 5 /nobreak >nul
start "" http://localhost:5173

echo Done. Close the AVW-Backend / AVW-Frontend windows to stop.
endlocal
