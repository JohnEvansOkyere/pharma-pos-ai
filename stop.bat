@echo off
title Pharma-POS-AI Shutdown
color 0C

echo ========================================
echo    STOPPING PHARMA-POS-AI...
echo ========================================
echo.

cd /d "%~dp0"

docker-compose down

echo.
echo ========================================
echo    PHARMA-POS-AI STOPPED!
echo ========================================
echo.
pause