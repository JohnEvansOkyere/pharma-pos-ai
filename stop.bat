@echo off
setlocal
title Pharma-POS-AI Shutdown
color 0C

echo ========================================
echo    STOPPING PHARMA-POS-AI...
echo ========================================
echo.

taskkill /FI "WINDOWTITLE eq Pharma POS Backend*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Pharma POS Frontend*" /T /F >nul 2>&1

echo.
echo ========================================
echo    PHARMA-POS-AI STOPPED!
echo ========================================
echo.
pause
