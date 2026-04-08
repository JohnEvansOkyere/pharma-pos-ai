@echo off
title Pharma-POS-AI Restore
color 0C

echo ========================================
echo    DATABASE RESTORE
echo ========================================
echo.
echo WARNING: This will overwrite the current database.
echo.

cd /d "%~dp0"

set POSTGRES_HOST=localhost
set POSTGRES_PORT=5432
set POSTGRES_DB=pharma_pos
set POSTGRES_USER=pharma_user
set POSTGRES_PASSWORD=newpassword123

for /f "usebackq tokens=1,* delims==" %%A in ("backend\.env") do (
    if /I "%%A"=="POSTGRES_HOST" set POSTGRES_HOST=%%B
    if /I "%%A"=="POSTGRES_PORT" set POSTGRES_PORT=%%B
    if /I "%%A"=="POSTGRES_DB" set POSTGRES_DB=%%B
    if /I "%%A"=="POSTGRES_USER" set POSTGRES_USER=%%B
    if /I "%%A"=="POSTGRES_PASSWORD" set POSTGRES_PASSWORD=%%B
)

if "%~1"=="" (
    echo Usage:
    echo   restore.bat backups\your_backup_file.dump
    echo.
    pause
    exit /b 1
)

set BACKUP_FILE=%~1

if not exist "%BACKUP_FILE%" (
    echo Backup file not found: %BACKUP_FILE%
    pause
    exit /b 1
)

set /p CONFIRM=Type RESTORE to continue: 
if /I not "%CONFIRM%"=="RESTORE" (
    echo Restore cancelled.
    pause
    exit /b 1
)

set PGPASSWORD=%POSTGRES_PASSWORD%
pg_restore -h %POSTGRES_HOST% -p %POSTGRES_PORT% -U %POSTGRES_USER% -d %POSTGRES_DB% --clean --if-exists --no-owner --no-privileges "%BACKUP_FILE%"

if %errorlevel% equ 0 (
    echo.
    echo Restore successful.
) else (
    echo.
    echo Restore failed!
)

set PGPASSWORD=
pause
