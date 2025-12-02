@echo off
cd /d "%~dp0"

if not exist .env (
    copy .env.example .env
    
    REM Generate random password (simple version)
    set "chars=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    set "password="
    for /L %%i in (1,1,16) do (
        set /a "rand=!random! %% 62"
        for %%j in (!rand!) do set "password=!password!!chars:~%%j,1!"
    )
    
    REM Replace placeholder password in .env
    powershell -Command "(Get-Content .env) -replace 'CHANGE_THIS_PASSWORD', '%password%' | Set-Content .env"
)