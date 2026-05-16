@echo off
setlocal
title Pharma-POS-AI Admin Provisioning
color 0B

cd /d "%~dp0"

echo ========================================
echo   ADMIN PROVISIONING
echo ========================================
echo.

docker inspect pharma-pos-backend >nul 2>&1
if errorlevel 1 (
    echo Backend container is not running.
    echo Start the application first with: docker compose -f docker-compose.client.yml up -d
    pause
    exit /b 1
)

docker exec -it pharma-pos-backend python scripts/provision_admin.py
set EXIT_CODE=%ERRORLEVEL%

echo.
if %EXIT_CODE% equ 0 (
    echo Admin provisioning completed successfully.
) else (
    echo Admin provisioning failed.
)

pause
exit /b %EXIT_CODE%
