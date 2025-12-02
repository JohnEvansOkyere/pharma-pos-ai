@echo off
title Pharma-POS-AI Startup
color 0A

echo ========================================
echo    PHARMA-POS-AI STARTING...
echo ========================================
echo.

cd /d "%~dp0"

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo Docker Desktop is not running!
    echo Please start Docker Desktop and try again.
    echo.
    pause
    exit /b 1
)

echo [1/4] Checking environment configuration...
if not exist .env (
    echo Creating environment file from template...
    copy .env.example .env
)

echo [2/4] Starting database...
docker-compose up -d db
timeout /t 10 /nobreak >nul

echo [3/4] Starting backend API...
docker-compose up -d backend
timeout /t 15 /nobreak >nul

echo [4/4] Starting frontend...
docker-compose up -d frontend
timeout /t 10 /nobreak >nul

echo.
echo ========================================
echo    PHARMA-POS-AI STARTED!
echo ========================================
echo.
echo Opening browser in 3 seconds...
timeout /t 3 /nobreak >nul

start http://localhost:8080

echo.
echo System is running!
echo - Frontend: http://localhost:8080
echo - API Docs: http://localhost:8000/docs
echo - Database Admin: http://localhost:8081
echo.
echo Press any key to close this window...
pause >nul