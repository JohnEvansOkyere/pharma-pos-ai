@echo off
title Pharma-POS-AI Backup
color 0B

echo ========================================
echo    DATABASE BACKUP
echo ========================================
echo.

cd /d "%~dp0"

REM Create backups directory
if not exist "backups" mkdir backups

REM Generate timestamp
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set TIMESTAMP=%datetime:~0,8%_%datetime:~8,6%

set BACKUP_FILE=backups\pharma_pos_backup_%TIMESTAMP%.sql

echo Creating backup: %BACKUP_FILE%
docker-compose exec -T db pg_dump -U pharma_user pharma_pos > %BACKUP_FILE%

if %errorlevel% equ 0 (
    echo.
    echo Backup successful: %BACKUP_FILE%
) else (
    echo.
    echo Backup failed!
)

pause