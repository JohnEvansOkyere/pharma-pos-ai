@echo off
setlocal
title Pharma-POS-AI Startup
color 0A

cd /d "%~dp0"

set "BACKEND_PYTHON=%~dp0backend\venv\Scripts\python.exe"
if not exist "%BACKEND_PYTHON%" set "BACKEND_PYTHON=python"

if not exist "%~dp0frontend\dist\index.html" (
    echo Frontend build not found at:
    echo %~dp0frontend\dist
    echo.
    echo Build the frontend before using the local launcher.
    pause
    exit /b 1
)

echo ========================================
echo    STARTING PHARMA-POS-AI
echo ========================================
echo.

start "Pharma POS Backend" cmd /k "cd /d ""%~dp0backend"" && ""%BACKEND_PYTHON%"" -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
timeout /t 3 /nobreak >nul
start "Pharma POS Frontend" cmd /k "cd /d ""%~dp0frontend\dist"" && ""%BACKEND_PYTHON%"" -m http.server 8080"
timeout /t 2 /nobreak >nul

start "" http://127.0.0.1:8080

echo Backend:  http://127.0.0.1:8000
echo Frontend: http://127.0.0.1:8080
echo.
echo Use stop.bat to close local launcher windows.
echo.
exit /b 0
