@echo off
setlocal
title Pharma-POS-AI Backup Task Setup
color 0B

cd /d "%~dp0"

set TASK_NAME=Pharma POS AI Nightly Backup
set TASK_TIME=20:00
set TASK_COMMAND=cmd.exe /c "cd /d ""%~dp0"" && set PHARMA_BACKUP_NONINTERACTIVE=1 && call backup.bat >> ""%~dp0backups\backup.log"" 2>&1"

echo ========================================
echo   NIGHTLY BACKUP TASK SETUP
echo ========================================
echo.
echo Task Name : %TASK_NAME%
echo Run Time  : %TASK_TIME%
echo.

schtasks /Create /F /SC DAILY /TN "%TASK_NAME%" /TR "%TASK_COMMAND%" /ST %TASK_TIME%

if %errorlevel% equ 0 (
    echo.
    echo Backup schedule installed successfully.
    echo Nightly backups will run at %TASK_TIME%.
    echo.
    echo Backup folder:
    echo %~dp0backups
    echo.
    echo You can review logs in:
    echo %~dp0backups\backup.log
    echo.
    schtasks /Query /TN "%TASK_NAME%"
    exit /b 0
)

echo.
echo Failed to create the scheduled backup task.
echo Run this file as Administrator.
exit /b 1
