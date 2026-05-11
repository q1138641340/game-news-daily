@echo off
setlocal EnableExtensions

REM === Codepage: UTF-8 for Chinese log readability ===
chcp 65001 > nul

REM === Paths (absolute — no reliance on CWD or PATH) ===
set REPO=C:\Users\q1138\game-news-daily
set GIT=E:\Git\cmd\git.exe
set PYTHON=C:\Users\q1138\AppData\Local\Programs\Python\Python311\python.exe

REM === Set working directory (logs + file checks depend on this) ===
cd /d "%REPO%"

REM === Mutex: prevent overlapping runs corrupting git state ===
if exist "%REPO%\.task-lock" (
    echo [%date% %time%] ABORT: previous run still active >> "%REPO%\output\task-error.log"
    exit /b 0
)
echo RUNNING > "%REPO%\.task-lock"

REM === Cleanup from previously crashed runs ===
if exist "%REPO%\.git\index.lock" del "%REPO%\.git\index.lock" 2>nul
"%GIT%" -C "%REPO%" rebase --abort 2>nul
"%GIT%" -C "%REPO%" stash drop stash@{0} 2>nul

REM === SSH: prevent hang in Session 0 ===
REM   BatchMode=yes  → fail immediately if key needs passphrase (no hang)
REM   StrictHostKeyChecking=accept-new → auto-accept new host keys (no prompt hang)
REM   ConnectTimeout=30 → don't wait forever if network is down
set GIT_SSH_COMMAND=ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=30

REM === Step 0: Get ISO date ===
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set TODAY=%%I

REM === Step 1: git pull ===
set HOME=C:\Users\q1138
set GIT_CONFIG_NOSYSTEM=1
mkdir output 2>nul
"%GIT%" -C "%REPO%" pull origin main --rebase > output\git-pull.log 2>&1
if errorlevel 1 (
    echo [%date% %time%] git pull FAILED >> output\task-error.log
    echo --- git-pull.log content --- >> output\task-error.log
    type output\git-pull.log >> output\task-error.log 2>nul
    del "%REPO%\.task-lock" 2>nul
    exit /b 1
)
echo [%date% %time%] git pull OK >> output\task-error.log

REM === Step 2: Start Chrome (skip if already running) ===
tasklist /fi "ImageName eq chrome.exe" 2>nul | find /i "chrome.exe" >nul
if errorlevel 1 (
    start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --disable-gpu --disable-software-rasterizer --no-first-run --no-default-browser-check --profile-directory="Default"
    timeout /t 15 /nobreak > nul
) else (
    timeout /t 3 /nobreak > nul
)

REM === Step 3: Run collection ===
REM Exit codes: 0=OK/no-new-content, 2=OpenCLI-unavailable, 3=all-sources-failed
"%PYTHON%" "%REPO%\run-win-opencli.py" >> output\win-opencli.log 2>&1
set EXITCODE=%ERRORLEVEL%
if %EXITCODE% equ 2 (
    echo [%date% %time%] Collection SKIPPED: OpenCLI/Chrome unavailable ^(exit 2^) >> output\task-error.log
    del "%REPO%\.task-lock" 2>nul
    exit /b 1
)
if %EXITCODE% equ 3 (
    echo [%date% %time%] Collection FAILED: all sources errored ^(exit 3^) >> output\task-error.log
    del "%REPO%\.task-lock" 2>nul
    exit /b 1
)
if %EXITCODE% neq 0 (
    echo [%date% %time%] Collection FAILED ^(exit %EXITCODE%^) >> output\task-error.log
    del "%REPO%\.task-lock" 2>nul
    exit /b 1
)
echo [%date% %time%] Collection OK >> output\task-error.log

REM === Step 4: git push ===
if exist "output\.cache\opencli-pending.json" (
    "%GIT%" -C "%REPO%" add output/.cache/opencli-pending.json output/.cache/seen_items.json
    "%GIT%" -C "%REPO%" commit -m "sync: Win OpenCLI %TODAY%" >> output\git-pull.log 2>&1
    "%GIT%" -C "%REPO%" push origin main >> output\git-pull.log 2>&1
    if errorlevel 1 (
        echo [%date% %time%] git push FAILED >> output\task-error.log
        echo --- git-push error --- >> output\task-error.log
        type output\git-pull.log >> output\task-error.log 2>nul
    ) else (
        echo [%date% %time%] git push OK >> output\task-error.log
    )
) else (
    echo [%date% %time%] No pending data to push >> output\task-error.log
)

del "%REPO%\.task-lock" 2>nul
endlocal
