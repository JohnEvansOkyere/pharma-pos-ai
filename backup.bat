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
set POSTGRES_DB=pharma_pos
set POSTGRES_USER=pharma_user
set POSTGRES_PASSWORD=
set POSTGRES_HOST=localhost
set POSTGRES_PORT=5432
set DOCKER_CONTAINER=pharma-pos-db

for /f "usebackq tokens=1,* delims==" %%A in ("backend\.env") do (
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
set BACKUP_FILE_ABS=%~dp0%BACKUP_FILE%

REM Prefer Docker-based backup (no pg_dump installation required on the host).
REM Falls back to native pg_dump if Docker is not available or the container is not running.
set USE_DOCKER=0
docker inspect %DOCKER_CONTAINER% >nul 2>&1 && set USE_DOCKER=1

if "%USE_DOCKER%"=="1" (
    echo Creating backup via Docker container: %BACKUP_FILE%
    docker exec %DOCKER_CONTAINER% pg_dump -U %POSTGRES_USER% -d %POSTGRES_DB% -F c -f /tmp/pharma_backup.dump
    if errorlevel 1 goto backup_failed
    docker cp %DOCKER_CONTAINER%:/tmp/pharma_backup.dump "%BACKUP_FILE_ABS%"
    if errorlevel 1 goto backup_failed
    docker exec %DOCKER_CONTAINER% rm /tmp/pharma_backup.dump >nul 2>&1
) else (
    echo Creating backup via native pg_dump: %BACKUP_FILE%
    REM Native pg_dump connects to host port 5435 when PostgreSQL runs in Docker Compose.
    REM If PostgreSQL is installed natively (not in Docker), use port 5432.
    set PGPASSWORD=%POSTGRES_PASSWORD%
    pg_dump -h localhost -p 5435 -U %POSTGRES_USER% -d %POSTGRES_DB% -F c -f "%BACKUP_FILE_ABS%"
    if errorlevel 1 (
        REM Try port 5432 as fallback for native PostgreSQL installs
        pg_dump -h localhost -p 5432 -U %POSTGRES_USER% -d %POSTGRES_DB% -F c -f "%BACKUP_FILE_ABS%"
        if errorlevel 1 goto backup_failed
    )
    set PGPASSWORD=
)

> "%BACKUP_STATUS_FILE%" echo %BACKUP_FILE_ABS%
forfiles /p "backups" /m "%POSTGRES_DB%_backup_*.dump" /d -%BACKUP_RETENTION_DAYS% /c "cmd /c del /q @path" >nul 2>&1
echo.
echo Backup successful: %BACKUP_FILE%
echo Retention policy: keep %BACKUP_RETENTION_DAYS% day(s) of backups
if /I not "%PHARMA_BACKUP_NONINTERACTIVE%"=="1" pause
exit /b 0

:backup_failed
echo.
echo Backup failed!
set PGPASSWORD=
if /I not "%PHARMA_BACKUP_NONINTERACTIVE%"=="1" pause
exit /b 1
