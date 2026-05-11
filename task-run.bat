@echo off
setlocal EnableExtensions

REM ---- Step 0: Get ISO date ----
for /f %%I in ('powershell -Command "Get-Date -Format yyyy-MM-dd"') do set TODAY=%%I

REM ---- Step 1: git pull (full path + no system config) ----
mkdir output 2>nul
set GIT_CONFIG_NOSYSTEM=1
set HOME=C:\Users\q1138
"E:\Git\cmd\git.exe" -C "C:\Users\q1138\game-news-daily" pull origin main --rebase > output\git-pull.log 2>&1
if errorlevel 1 (
    echo [%date% %time%] git pull failed >> output\task-error.log
) else (
    echo [%date% %time%] git pull OK >> output\task-error.log
)

REM ---- Step 2: Start Chrome ----
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --profile-directory="Default"
timeout /t 10 /nobreak > nul

REM ---- Step 3: Run collection ----
"C:\Users\q1138\AppData\Local\Programs\Python\Python311\python.exe" "C:\Users\q1138\game-news-daily\run-win-opencli.py" >> output\win-opencli.log 2>&1
if errorlevel 1 (
    echo [%date% %time%] Collection failed (exit %ERRORLEVEL%) >> output\task-error.log
    exit /b 1
) else (
    echo [%date% %time%] Collection OK >> output\task-error.log
)

REM ---- Step 4: git push (only if collection succeeded) ----
if exist "output\.cache\opencli-pending.json" (
    "E:\Git\cmd\git.exe" -C "C:\Users\q1138\game-news-daily" add output/.cache/opencli-pending.json output/.cache/seen_items.json
    "E:\Git\cmd\git.exe" -C "C:\Users\q1138\game-news-daily" commit -m "sync: Win OpenCLI %TODAY%" >> output\git-pull.log 2>&1
    "E:\Git\cmd\git.exe" -C "C:\Users\q1138\game-news-daily" push origin main >> output\git-pull.log 2>&1
    if errorlevel 1 (
        echo [%date% %time%] git push failed >> output\task-error.log
    ) else (
        echo [%date% %time%] git push OK >> output\task-error.log
    )
)
endlocal