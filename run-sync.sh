#!/bin/bash
# Mac ↔ Win 协同工作流 — Mac 端脚本
# 1. git pull  拉取 Win 端推送的最新结果
# 2. 采集      运行工作流（如需要）
# 3. git push  推送变更回 GitHub
#
# 用法:  bash run-sync.sh [--collect]
#   --collect  执行采集（默认仅同步）
#   （无参数）  仅拉取最新结果 + 推送本地变更

set -e
cd "$(dirname "$0")"
WORKFLOW_DIR="$(pwd)"
VAULT_PATH="/Users/sunjinghe/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian Vault/game-news-daily"

echo "========================================"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Mac ↔ Win 协同同步"
echo "========================================"

# 加载环境变量
if [ -f "$WORKFLOW_DIR/.env" ]; then
  export $(grep -v '^#' "$WORKFLOW_DIR/.env" | xargs)
fi

# ---- Step 1: 拉取最新 ----
echo ""
echo "[Step 1/3] git pull 拉取最新代码和 Win 端结果..."
git pull origin main --rebase 2>&1 || echo "  ⚠️  git pull 有冲突，请手动处理"

# ---- Step 2: 采集（可选） ----
if [ "$1" = "--collect" ]; then
  echo ""
  echo "[Step 2/3] 运行本地采集..."

  mkdir -p output/.cache

  if [ -f "$WORKFLOW_DIR/.venv/bin/activate" ]; then
    source "$WORKFLOW_DIR/.venv/bin/activate"
  fi

  python main.py 2>&1 | tee output/workflow.log
  EXIT_CODE=${PIPESTATUS[0]}

  if [ $EXIT_CODE -ne 0 ]; then
    echo "  ❌ 采集失败 (exit $EXIT_CODE)"
  fi

  # 复制到 iCloud vault
  if [ -d "$VAULT_PATH" ]; then
    cp -r output/*/ "$VAULT_PATH/" 2>/dev/null || true
    echo "  ✅ 已复制日报到 iCloud vault"
  fi
else
  echo ""
  echo "[Step 2/3] 跳过采集（加 --collect 参数开启）"
fi

# ---- Step 3: 推送 ----
echo ""
echo "[Step 3/3] git push 推送变更..."

# 只推送 Mac 端的代码/配置修改，不推送 output（Win 会推）
git add -A
if git diff --cached --quiet; then
  echo "  无变更，跳过推送"
else
  git commit -m "sync: Mac 端同步 $(date '+%Y-%m-%d %H:%M')" 2>&1 || true
  git push origin main 2>&1
  echo "  ✅ 已推送"
fi

echo ""
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 同步完成"
