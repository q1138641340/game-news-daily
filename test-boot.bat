@echo off
setlocal EnableExtensions
echo [%date% %time%] Test boot run started >> output\test-boot.log
C:\Users\q1138\AppData\Local\Programs\Python\Python311\python.exe C:\Users\q1138\game-news-daily\run-win-opencli.py >> output\test-boot.log 2>&1
set EXITCODE=%ERRORLEVEL%
echo [%date% %time%] Test boot run finished, exit %EXITCODE% >> output\test-boot.log
schtasks /delete /tn "DailyNewsOpenCLI-TestBoot" /f 2>/dev/null
endlocal
