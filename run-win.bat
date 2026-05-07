@echo off
REM ============================================
REM Mac <-> Win 协同工作流 - Windows 端脚本
REM 1. git pull   拉取 Mac/GitHub Actions 最新变更
REM 2. Python采集 运行全量工作流（含 OpenCLI 源）
REM 3. git push   推送日报结果回 GitHub
REM
REM 用于 Windows Task Scheduler 每天 06:00 执行
REM GH Actions 02:30 开始，实测 04:00-04:09 完成，06:00 充裕安全窗口
REM ============================================

echo ========================================
echo [%date% %time%] Win 端协同采集
echo ========================================

cd /d "C:\Users\sunjinghe\game-news-daily"

REM ---- Step 0: 等待 GH Actions 完成 ----
echo.
echo [Step 0/4] 检查 GitHub Actions 是否已完成...

REM 获取当前日期
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value ^| find "="') do set TODAY=%%I
set TODAY=%TODAY:~0,4%-%TODAY:~4,2%-%TODAY:~6,2%

REM 尝试拉取，检查是否有今天的日报
git fetch origin main 2>nul
git log origin/main --oneline --since="%TODAY%T00:00:00" --grep="daily\|Daily\|report\|Report" -1 | findstr "." >nul
if %errorlevel% neq 0 (
    echo   WARNING: 未检测到今天的 GH Actions 日报，继续运行
) else (
    echo   OK: GH Actions 日报已就绪
)

REM ---- Chrome 预检 ----
echo.
echo [Step 0b/4] 检查 OpenCLI 扩展...
opencli doctor 2>&1 | findstr /C:"connected" >nul
if %errorlevel% neq 0 (
    echo   WARNING: OpenCLI 扩展未连接，中文期刊/小红书将跳过
) else (
    echo   OK: OpenCLI 扩展已连接
)

REM ---- Step 1: 拉取最新 ----
echo.
echo [Step 1/4] git pull 拉取最新代码...
git pull origin main --rebase
if %errorlevel% neq 0 (
    echo   WARNING: git pull 失败，继续用本地版本运行
)

REM ---- Step 2: OpenCLI 采集（仅万方/百度学术/小红书，不重复 GH 的工作）----
echo.
echo [Step 2/4] 运行 OpenCLI 采集...
mkdir output\.cache output\%TODAY% 2>nul

python run-win-opencli.py > output\win-opencli.log 2>&1
set EXIT_CODE=%errorlevel%

if %EXIT_CODE% neq 0 (
    echo   ERROR: 采集失败 (exit %EXIT_CODE%)
    type output\win-opencli.log | findstr /C:"ERROR" /C:"失败"
) else (
    echo   OK: 万方/百度学术/小红书 采集完成
)

REM ---- Step 3: 推送结果 ----
echo.
echo [Step 3/4] git push 推送补充内容...
git add output\ *.yaml *.md run-win-opencli.py 2>nul
git commit -m "sync: Win OpenCLI 补充内容 %date%" 2>nul
git push origin main 2>&1
if %errorlevel% neq 0 (
    echo   WARNING: git push 失败
) else (
    echo   OK: 已推送到 GitHub
)

REM ---- Step 4: 完成 ----
echo.
echo [Step 4/4] 完成
echo [%date% %time%] 退出码: %EXIT_CODE%
