@echo off
setlocal
cd /d "%~dp0"

set "BACKEND_ENV=backend\.env"
set "FRONTEND_ENV=frontend\.env.local"

if not exist "backend" (
    echo backend folder not found.
    exit /b 1
)

set "PHARMACY_NAME=Pharma POS AI"
set "POSTGRES_PASSWORD_VALUE=changeme123"

if not "%PHARMA_SETUP_NONINTERACTIVE%"=="1" (
    set /p PHARMACY_NAME=Enter pharmacy name [Pharma POS AI]:
    if "%PHARMACY_NAME%"=="" set "PHARMACY_NAME=Pharma POS AI"

    set /p POSTGRES_PASSWORD_VALUE=Enter PostgreSQL password for pharma_user:
    if "%POSTGRES_PASSWORD_VALUE%"=="" (
        echo PostgreSQL password cannot be empty.
        exit /b 1
    )
)

if not exist "%BACKEND_ENV%" (
    if exist ".env.example" (
        powershell -NoProfile -ExecutionPolicy Bypass -Command "$secret=[guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N'); $content = Get-Content '.env.example'; $content = $content -replace '^POSTGRES_PASSWORD=.*$', ('POSTGRES_PASSWORD=' + '%POSTGRES_PASSWORD_VALUE%'); $content = $content -replace '^SECRET_KEY=.*$', ('SECRET_KEY=' + $secret); $content = $content -replace '^APP_NAME=.*$', ('APP_NAME=' + '%PHARMACY_NAME%'); $content = $content -replace '^VITE_API_URL=.*$', 'VITE_API_URL=http://localhost:8000/api'; Set-Content '%BACKEND_ENV%' $content"
    ) else (
        > "%BACKEND_ENV%" echo DATABASE_BACKEND=postgresql
        >> "%BACKEND_ENV%" echo DATABASE_URL=
        >> "%BACKEND_ENV%" echo POSTGRES_HOST=localhost
        >> "%BACKEND_ENV%" echo POSTGRES_PORT=5432
        >> "%BACKEND_ENV%" echo POSTGRES_DB=pharma_pos
        >> "%BACKEND_ENV%" echo POSTGRES_USER=pharma_user
        >> "%BACKEND_ENV%" echo POSTGRES_PASSWORD=%POSTGRES_PASSWORD_VALUE%
        for /f %%I in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "[guid]::NewGuid().ToString(''N'') + [guid]::NewGuid().ToString(''N'')"') do set "GENERATED_SECRET=%%I"
        >> "%BACKEND_ENV%" echo SECRET_KEY=%GENERATED_SECRET%
        >> "%BACKEND_ENV%" echo ALGORITHM=HS256
        >> "%BACKEND_ENV%" echo ACCESS_TOKEN_EXPIRE_MINUTES=30
        >> "%BACKEND_ENV%" echo APP_NAME=%PHARMACY_NAME%
        >> "%BACKEND_ENV%" echo APP_VERSION=1.0.0
        >> "%BACKEND_ENV%" echo DEBUG=False
        >> "%BACKEND_ENV%" echo ENVIRONMENT=production
        >> "%BACKEND_ENV%" echo BACKEND_CORS_ORIGINS=["http://localhost:3000","http://localhost:5173","http://localhost:8000","http://localhost:8080","http://localhost"]
        >> "%BACKEND_ENV%" echo ENABLE_BACKGROUND_SCHEDULER=True
        >> "%BACKEND_ENV%" echo TIMEZONE=Africa/Accra
        >> "%BACKEND_ENV%" echo LOG_LEVEL=INFO
        >> "%BACKEND_ENV%" echo LOG_FILE=./logs/app.log
    )
)

if not exist "%FRONTEND_ENV%" (
    > "%FRONTEND_ENV%" echo VITE_API_URL=http://localhost:8000/api
)

echo Environment files prepared:
echo   %BACKEND_ENV%
echo   %FRONTEND_ENV%
echo.
echo Review backend\.env before client handover, especially:
echo   APP_NAME=%PHARMACY_NAME%
echo   POSTGRES_PASSWORD
echo   SECRET_KEY
exit /b 0
