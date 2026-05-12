@echo off
setlocal EnableExtensions

REM === Mutex: prevent overlapping runs ===
if exist "C:\Users\q1138\game-news-daily\.task-lock" (
    echo [%date% %time%] ABORT: previous run still active >> "C:\Users\q1138\game-news-daily\output\task-error.log"
    exit /b 0
)
echo RUNNING > "C:\Users\q1138\game-news-daily\.task-lock"

REM === Cleanup from previously crashed runs ===
if exist "C:\Users\q1138\game-news-daily\.git\index.lock" del "C:\Users\q1138\game-news-daily\.git\index.lock" 2>nul
"E:\Git\cmd\git.exe" -C "C:\Users\q1138\game-news-daily" rebase --abort 2>nul
"E:\Git\cmd\git.exe" -C "C:\Users\q1138\game-news-daily" stash drop stash@{0} 2>nul

REM === Environment: no system gitconfig, HOME for .gitconfig ===
set HOME=C:\Users\q1138
set GIT_CONFIG_NOSYSTEM=1
set GIT_SSH_COMMAND=ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=30

REM === Set working directory ===
cd /d "C:\Users\q1138\game-news-daily"
mkdir output 2>nul

REM === Step 1: git pull ===
"E:\Git\cmd\git.exe" -C "C:\Users\q1138\game-news-daily" pull origin main --rebase > "C:\Users\q1138\game-news-daily\output\git-pull.log" 2>&1
if errorlevel 1 (
    echo [%date% %time%] git pull FAILED >> "C:\Users\q1138\game-news-daily\output\task-error.log"
    type "C:\Users\q1138\game-news-daily\output\git-pull.log" >> "C:\Users\q1138\game-news-daily\output\task-error.log" 2>nul
    del "C:\Users\q1138\game-news-daily\.task-lock" 2>nul
    exit /b 1
)
echo [%date% %time%] git pull OK >> "C:\Users\q1138\game-news-daily\output\task-error.log"

REM === Step 2: Start Chrome (skip if already running) ===
tasklist /fi "ImageName eq chrome.exe" 2>nul | find /i "chrome.exe" >nul
if errorlevel 1 (
    start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --disable-gpu --disable-software-rasterizer --no-first-run --no-default-browser-check --profile-directory="Default"
    timeout /t 15 /nobreak > nul
) else (
    timeout /t 3 /nobreak > nul
)

REM === Step 3: Run collection ===
"C:\Users\q1138\AppData\Local\Programs\Python\Python311\python.exe" "C:\Users\q1138\game-news-daily\run-win-opencli.py" >> "C:\Users\q1138\game-news-daily\output\win-opencli.log" 2>&1
if errorlevel 1 (
    echo [%date% %time%] Collection FAILED ^(exit %ERRORLEVEL%^) >> "C:\Users\q1138\game-news-daily\output\task-error.log"
    del "C:\Users\q1138\game-news-daily\.task-lock" 2>nul
    exit /b 1
)
echo [%date% %time%] Collection OK >> "C:\Users\q1138\game-news-daily\output\task-error.log"

REM === Step 4: git push ===
if exist "C:\Users\q1138\game-news-daily\output\.cache\opencli-pending.json" (
    "E:\Git\cmd\git.exe" -C "C:\Users\q1138\game-news-daily" add output/.cache/opencli-pending.json output/.cache/seen_items.json
    "E:\Git\cmd\git.exe" -C "C:\Users\q1138\game-news-daily" commit -m "sync: Win OpenCLI 2026-05-12" >> "C:\Users\q1138\game-news-daily\output\git-pull.log" 2>&1
    "E:\Git\cmd\git.exe" -C "C:\Users\q1138\game-news-daily" push origin main >> "C:\Users\q1138\game-news-daily\output\git-pull.log" 2>&1
    if errorlevel 1 (
        echo [%date% %time%] git push FAILED >> "C:\Users\q1138\game-news-daily\output\task-error.log"
    ) else (
        echo [%date% %time%] git push OK >> "C:\Users\q1138\game-news-daily\output\task-error.log"
    )
)

del "C:\Users\q1138\game-news-daily\.task-lock" 2>nul
endlocal
