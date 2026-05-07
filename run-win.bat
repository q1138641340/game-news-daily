@echo off
REM ============================================
REM Mac <-> Win 协同工作流 - Windows 端脚本
REM 1. git pull   拉取 Mac/GitHub Actions 最新变更
REM 2. Python采集 运行全量工作流（含 OpenCLI 源）
REM 3. git push   推送日报结果回 GitHub
REM
REM 用于 Windows Task Scheduler 每天 03:00 执行
REM ============================================

echo ========================================
echo [%date% %time%] Win 端协同采集
echo ========================================

cd /d "C:\Users\sunjinghe\game-news-daily"

REM ---- Step 0: Chrome 预检 ----
echo.
echo [Step 0/4] 检查 OpenCLI 扩展...
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

REM ---- Step 2: 采集 ----
echo.
echo [Step 2/4] 运行全量采集...
mkdir output\.cache 2>nul

python main.py > output\workflow.log 2>&1
set EXIT_CODE=%errorlevel%

if %EXIT_CODE% neq 0 (
    echo   ERROR: 采集失败 (exit %EXIT_CODE%)
    type output\workflow.log | findstr /C:"ERROR" /C:"失败"
)

REM ---- Step 3: 推送结果 ----
echo.
echo [Step 3/4] git push 推送日报...
git add output\ *.yaml *.md 2>nul
git commit -m "sync: Win 端采集结果 %date%" 2>nul
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
