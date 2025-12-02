@echo off
title Pharma-POS-AI Uninstall
color 0C

echo ========================================
echo    PHARMA-POS-AI UNINSTALL
echo ========================================
echo.
echo This will stop and remove all containers.
echo Your data will be preserved unless you choose to delete it.
echo.

set /p confirm="Continue with uninstall? (Y/N): "
if /i not "%confirm%"=="Y" exit /b

cd /d "%~dp0"

echo.
echo Stopping containers...
docker-compose down

echo.
set /p deletedata="Delete all data including database? (Y/N): "
if /i "%deletedata%"=="Y" (
    echo Removing all data...
    docker-compose down -v
    echo All data deleted.
) else (
    echo Data preserved. You can reinstall without losing data.
)

echo.
echo Uninstall complete.
timeout /t 5