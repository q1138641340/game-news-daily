@echo off
setlocal EnableExtensions

REM === Mutex ===
if exist C:\Users\q1138\game-news-daily\.task-lock (
    echo ABORT >> output\task-error.log
    exit /b 0
)
echo RUNNING > C:\Users\q1138\game-news-daily\.task-lock

REM === Cleanup ===
if exist C:\Users\q1138\game-news-daily\.git\index.lock del C:\Users\q1138\game-news-daily\.git\index.lock 2>nul
E:\Git\cmd\git.exe -C C:\Users\q1138\game-news-daily rebase --abort 2>nul
E:\Git\cmd\git.exe -C C:\Users\q1138\game-news-daily stash drop stash@{0} 2>nul

REM === Environment ===
set HOME=C:\Users\q1138
set GIT_CONFIG_NOSYSTEM=1
set GIT_SSH_COMMAND=ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=30

cd /d C:\Users\q1138\game-news-daily
mkdir output 2>nul

REM === Step 1: git pull ===
E:\Git\cmd\git.exe -C C:\Users\q1138\game-news-daily pull origin main --rebase > output\git-pull.log 2>&1
if errorlevel 1 (
    echo git pull FAILED >> output\task-error.log
    type output\git-pull.log >> output\task-error.log 2>nul
    del C:\Users\q1138\game-news-daily\.task-lock 2>nul
    exit /b 1
)
echo git pull OK >> output\task-error.log

REM === Step 2: Chrome ===
tasklist /fi "ImageName eq chrome.exe" 2>nul | find /i "chrome.exe" >nul
if errorlevel 1 (
    start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --disable-gpu --no-first-run --no-default-browser-check --profile-directory="Default"
    timeout /t 15 /nobreak > nul
) else (
    timeout /t 3 /nobreak > nul
)

REM === Step 3: Collection ===
C:\Users\q1138\AppData\Local\Programs\Python\Python311\python.exe C:\Users\q1138\game-news-daily\run-win-opencli.py >> output\win-opencli.log 2>&1
if errorlevel 1 (
    echo Collection FAILED >> output\task-error.log
    del C:\Users\q1138\game-news-daily\.task-lock 2>nul
    exit /b 1
)
echo Collection OK >> output\task-error.log

REM === Step 4: git push ===
if exist C:\Users\q1138\game-news-daily\output\.cache\opencli-pending.json (
    E:\Git\cmd\git.exe -C C:\Users\q1138\game-news-daily add output/.cache/opencli-pending.json output/.cache/seen_items.json
    E:\Git\cmd\git.exe -C C:\Users\q1138\game-news-daily commit -m "sync: Win OpenCLI" >> output\git-pull.log 2>&1
    E:\Git\cmd\git.exe -C C:\Users\q1138\game-news-daily push origin main >> output\git-pull.log 2>&1
    if errorlevel 1 (
        echo git push FAILED >> output\task-error.log
    ) else (
        echo git push OK >> output\task-error.log
    )
)

del C:\Users\q1138\game-news-daily\.task-lock 2>nul
endlocal
