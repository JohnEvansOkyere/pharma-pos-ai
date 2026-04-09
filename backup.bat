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
set BACKUP_RETENTION_DAYS=30
set BACKUP_STATUS_FILE=backups\latest_backup.txt

REM Load database settings from backend\.env when available
set POSTGRES_HOST=localhost
set POSTGRES_PORT=5432
set POSTGRES_DB=pharma_pos
set POSTGRES_USER=pharma_user
set POSTGRES_PASSWORD=

for /f "usebackq tokens=1,* delims==" %%A in ("backend\.env") do (
    if /I "%%A"=="POSTGRES_HOST" set POSTGRES_HOST=%%B
    if /I "%%A"=="POSTGRES_PORT" set POSTGRES_PORT=%%B
    if /I "%%A"=="POSTGRES_DB" set POSTGRES_DB=%%B
    if /I "%%A"=="POSTGRES_USER" set POSTGRES_USER=%%B
    if /I "%%A"=="POSTGRES_PASSWORD" set POSTGRES_PASSWORD=%%B
    if /I "%%A"=="BACKUP_RETENTION_DAYS" set BACKUP_RETENTION_DAYS=%%B
)

if "%POSTGRES_PASSWORD%"=="" (
    echo POSTGRES_PASSWORD is not configured. Update backend\.env before running backups.
    if /I not "%PHARMA_BACKUP_NONINTERACTIVE%"=="1" pause
    exit /b 1
)

REM Generate timestamp
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set TIMESTAMP=%datetime:~0,8%_%datetime:~8,6%

set BACKUP_FILE=backups\%POSTGRES_DB%_backup_%TIMESTAMP%.dump

echo Creating backup: %BACKUP_FILE%
set PGPASSWORD=%POSTGRES_PASSWORD%
pg_dump -h %POSTGRES_HOST% -p %POSTGRES_PORT% -U %POSTGRES_USER% -d %POSTGRES_DB% -F c -f "%BACKUP_FILE%"

if %errorlevel% equ 0 (
    > "%BACKUP_STATUS_FILE%" echo %BACKUP_FILE%
    forfiles /p "backups" /m "%POSTGRES_DB%_backup_*.dump" /d -%BACKUP_RETENTION_DAYS% /c "cmd /c del /q @path" >nul 2>&1
    echo.
    echo Backup successful: %BACKUP_FILE%
    echo Retention policy: keep %BACKUP_RETENTION_DAYS% day(s) of backups
) else (
    echo.
    echo Backup failed!
)

set PGPASSWORD=
if /I not "%PHARMA_BACKUP_NONINTERACTIVE%"=="1" pause
