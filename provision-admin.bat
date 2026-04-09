@echo off
setlocal
title Pharma-POS-AI Admin Provisioning
color 0B

cd /d "%~dp0"

set "BACKEND_PYTHON=%~dp0backend\venv\Scripts\python.exe"
if not exist "%BACKEND_PYTHON%" set "BACKEND_PYTHON=python"

echo ========================================
echo   LOCAL ADMIN PROVISIONING
echo ========================================
echo.

"%BACKEND_PYTHON%" scripts\provision_admin.py
set EXIT_CODE=%ERRORLEVEL%

echo.
if %EXIT_CODE% equ 0 (
    echo Admin provisioning completed successfully.
) else (
    echo Admin provisioning failed.
)

pause
exit /b %EXIT_CODE%
