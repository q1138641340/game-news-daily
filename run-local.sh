#!/bin/bash
# game-news-daily 本地运行脚本
# 输出到 iCloud vault

VAULT_PATH="/Users/sunjinghe/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian Vault/game-news-daily"
WORKFLOW_DIR="/Users/sunjinghe/daily-news-workflow"
OUTPUT_DIR="$WORKFLOW_DIR/output"

# 记录开始时间
echo "[$(date)] game-news-daily 工作流开始..."

# 进入工作目录
cd "$WORKFLOW_DIR" || exit 1

# 清理旧输出
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR/papers"

# 加载环境变量
if [ -f "$WORKFLOW_DIR/.env" ]; then
  export $(grep -v '^#' "$WORKFLOW_DIR/.env" | xargs)
fi

# 运行工作流
python main.py 2>&1 | tee "$WORKFLOW_DIR/output/workflow.log"
EXIT_CODE=${PIPESTATUS[0]}

# 如果成功，复制到 iCloud vault
if [ $EXIT_CODE -eq 0 ]; then
  if [ -d "$OUTPUT_DIR" ] && [ "$(ls -A "$OUTPUT_DIR" 2>/dev/null)" ]; then
    mkdir -p "$VAULT_PATH"
    cp -r "$OUTPUT_DIR"/* "$VAULT_PATH/"
    echo "[$(date)] 已同步到 iCloud vault: $VAULT_PATH"
  fi
else
  echo "[$(date)] 工作流失败，退出码: $EXIT_CODE"
fi

echo "[$(date)] 工作流完成，退出码: $EXIT_CODE"
