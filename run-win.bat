@echo off
chcp 65001 > nul
REM ============================================
REM Win 端 OpenCLI 采集脚本
REM 1. git pull  拉取最新代码
REM 2. OpenCLI   万方 + 百度学术 + 小红书
REM 3. git push  推送 pending 数据（含 3 次重试）
REM
REM Task Scheduler: 每天 06:00 北京时间
REM ============================================

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo ========================================
echo [%date% %time%] Win OpenCLI 采集
echo ========================================

REM ---- Step 0: 获取 ISO 日期 + GH Actions 完成检查 ----
echo.
echo [Step 0/4] 日期 & GH Actions 检查...
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value ^| find "="') do set TODAY=%%I
set TODAY=%TODAY:~0,4%-%TODAY:~4,2%-%TODAY:~6,2%

git fetch origin main 2>nul
git log origin/main --oneline --since="%TODAY%T00:00:00" --grep="daily\|Daily\|report\|Report" -1 | findstr "." >nul
if %errorlevel% neq 0 (
    echo   WARNING: 未检测到 %TODAY% 的 GH Actions 日报
) else (
    echo   OK: %TODAY% GH Actions 日报已就绪
)

REM ---- Step 0b: Chrome + OpenCLI 预检 ----
echo.
echo [Step 0b/4] OpenCLI 扩展检查...
opencli doctor 2>&1 | findstr /C:"connected" >nul
if %errorlevel% neq 0 (
    echo   WARNING: OpenCLI 未连接，尝试重启 daemon...
    opencli daemon restart 2>nul
    timeout /t 3 /nobreak >nul
    opencli doctor 2>&1 | findstr /C:"connected" >nul
    if %errorlevel% neq 0 (
        echo   ERROR: OpenCLI 不可用，本次跳过
        goto :done
    )
)
echo   OK: OpenCLI 已连接

REM ---- Step 1: git pull ----
echo.
echo [Step 1/4] git pull...
git pull origin main --rebase
if %errorlevel% neq 0 (
    echo   WARNING: git pull 失败，继续
)

REM ---- Step 2: OpenCLI 采集 ----
echo.
echo [Step 2/4] OpenCLI 采集 (万方/百度学术/小红书)...
mkdir output\.cache 2>nul

python run-win-opencli.py > output\win-opencli.log 2>&1
set EXIT_CODE=%errorlevel%

if %EXIT_CODE% neq 0 (
    echo   ERROR: 采集失败 (exit %EXIT_CODE%)
    type output\win-opencli.log | findstr /C:"ERROR" /C:"失败"
    goto :done
)
echo   OK: 采集完成

REM ---- Step 3: git push (3 次重试) ----
echo.
echo [Step 3/4] git push...

set RETRY=0
:push_retry
git add -f output\.cache\ output\.cache\opencli-pending.json output\.cache\seen_items.json 2>nul
git commit -m "sync: Win OpenCLI %TODAY%" 2>nul

git push origin main 2>&1
if %errorlevel% equ 0 (
    echo   OK: 已推送到 GitHub
    goto :done
)

set /a RETRY+=1
if %RETRY% lss 3 (
    echo   推送失败，重试 %RETRY%/3...
    timeout /t 10 /nobreak >nul
    git pull origin main --rebase 2>nul
    goto :push_retry
)
echo   ERROR: push 失败 3 次

REM ---- Step 4: 完成 ----
:done
echo.
echo [Step 4/4] 完成 [%TODAY% %time%] 退出码: %EXIT_CODE%
