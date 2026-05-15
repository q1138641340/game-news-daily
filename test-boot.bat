@echo off
setlocal EnableExtensions

echo RUNNING > C:\Users\q1138\game-news-daily\.task-lock
echo [%date% %time%] Test boot run started >> output\test-boot.log

set HOME=C:\Users\q1138
set GIT_CONFIG_NOSYSTEM=1
set GIT_SSH_COMMAND=ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=30

REM === git pull ===
E:\Git\cmd\git.exe -C C:\Users\q1138\game-news-daily pull origin main --rebase > output\git-pull.log 2>&1
if errorlevel 1 (
    echo [%date% %time%] git pull FAILED >> output\test-boot.log
    type output\git-pull.log >> output\test-boot.log 2>nul
    del C:\Users\q1138\game-news-daily\.task-lock 2>nul
    exit /b 1
)
echo [%date% %time%] git pull OK >> output\test-boot.log

REM === git push ===
E:\Git\cmd\git.exe -C C:\Users\q1138\game-news-daily add output/.cache/opencli-pending.json output/.cache/seen_items.json >> output\test-boot.log 2>&1
E:\Git\cmd\git.exe -C C:\Users\q1138\game-news-daily commit -m "sync: Win OpenCLI test-boot" >> output\test-boot.log 2>&1
if errorlevel 1 (
    echo [%date% %time%] git push FAILED >> output\test-boot.log
    type output\git-pull.log >> output\test-boot.log 2>nul
) else (
    echo [%date% %time%] git push OK >> output\test-boot.log
)

echo [%date% %time%] Test boot run finished >> output\test-boot.log
del C:\Users\q1138\game-news-daily\.task-lock 2>nul
endlocal