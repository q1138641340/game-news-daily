@echo off
REM Screen ON requires manual keypress after wake (not possible from scheduled task)
cd /d "%LOCALAPPDATA%\..\..\game-news-daily" 2>nul || cd /d "C:\Users\q1138\game-news-daily"

REM Pull latest code before running
git pull origin main > nul 2>&1

REM Start Chrome for OpenCLI extension
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --profile-directory="Default"
timeout /t 10 /nobreak > nul

REM Run collection
"C:\Users\q1138\AppData\Local\Programs\Python\Python311\python.exe" run-win-opencli.py
set EXIT_CODE=%ERRORLEVEL%

REM Git push
if exist "output\.cache\opencli-pending.json" (
    git add output\.cache\opencli-pending.json output\.cache\seen_items.json 2>nul
    for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value ^| find "="') do set TODAY=%%I
    set TODAY=%TODAY:~0,4%-%TODAY:~4,2%-%TODAY:~6,2%
    git commit -m "sync: Win OpenCLI %TODAY%" 2>nul
    git push origin main 2>nul
)

REM Sleep only if collection succeeded
if %EXIT_CODE% equ 0 (
    rundll32.exe powrprof.dll,SetSuspendState 0,1,0
) else (
    echo [%date% %time%] Collection failed (exit %EXIT_CODE%) >> output\task-error.log
)