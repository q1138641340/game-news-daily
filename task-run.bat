@echo off
setlocal
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%" 2>nul || cd /d "C:\Users\q1138\game-news-daily"

REM ---- Step 0: Get ISO date ----
for /f %%I in ('powershell -Command "Get-Date -Format 'yyyy-MM-dd'"') do set TODAY=%%I

REM ---- Step 1: git pull ----
mkdir output 2>nul
git pull origin main --rebase > output\git-pull.log 2>&1
if %errorlevel% neq 0 (
    echo [%date% %time%] git pull failed >> output\task-error.log
)

REM ---- Step 2: Start Chrome ----
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --profile-directory="Default"
timeout /t 10 /nobreak > nul

REM ---- Step 3: Run collection ----
"C:\Users\q1138\AppData\Local\Programs\Python\Python311\python.exe" run-win-opencli.py
set EXIT_CODE=%ERRORLEVEL%

REM ---- Step 4: git push (only if collection succeeded) ----
if %EXIT_CODE% equ 0 (
    if exist "output\.cache\opencli-pending.json" (
        git add output/.cache/opencli-pending.json output/.cache/seen_items.json 2>nul
        git commit -m "sync: Win OpenCLI %TODAY%" 2>nul
        git push origin main 2>nul
        if %errorlevel% neq 0 (
            echo [%date% %time%] git push failed >> output\task-error.log
        )
    ) else (
        echo [%date% %time%] No pending data to push >> output\task-error.log
    )
    REM ---- Sleep ----
    rundll32.exe powrprof.dll,SetSuspendState 0,1,0
) else (
    echo [%date% %time%] Collection failed (exit %EXIT_CODE%) >> output\task-error.log
)
endlocal