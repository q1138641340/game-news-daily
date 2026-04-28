#!/bin/bash
# game-news-daily 本地运行脚本
# 输出到 iCloud vault

VAULT_PATH="/Users/sunjinghe/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian Vault/game-news-daily"
WORKFLOW_DIR="/Users/sunjinghe/daily-news-workflow"
LAST_RUN_FILE="$WORKFLOW_DIR/.last_run"
LOG_FILE="$WORKFLOW_DIR/output/workflow.log"

# 检查是否超过 24 小时没运行
should_run() {
    if [ ! -f "$LAST_RUN_FILE" ]; then
        return 0  # 从未运行过，需要运行
    fi

    last_run=$(cat "$LAST_RUN_FILE")
    now=$(date +%s)
    diff=$((now - last_run))

    # 超过 24 小时（86400 秒）
    if [ $diff -gt 86400 ]; then
        return 0
    else
        echo "上次运行: $((diff/3600)) 小时前，不需要重复运行"
        return 1
    fi
}

# 执行工作流
do_run() {
    echo "[$(date)] game-news-daily 工作流开始..."

    # 进入工作目录
    cd "$WORKFLOW_DIR" || exit 1

    # 清理旧输出
    rm -rf "$WORKFLOW_DIR/output"
    mkdir -p "$WORKFLOW_DIR/output/papers"

    # 加载环境变量
    if [ -f "$WORKFLOW_DIR/.env" ]; then
        export $(grep -v '^#' "$WORKFLOW_DIR/.env" | xargs)
    fi

    # 运行工作流
    python main.py 2>&1 | tee "$LOG_FILE"
    EXIT_CODE=${PIPESTATUS[0]}

    # 成功则更新运行时间并复制到 vault
    if [ $EXIT_CODE -eq 0 ]; then
        date +%s > "$LAST_RUN_FILE"
        if [ -d "$WORKFLOW_DIR/output" ] && [ "$(ls -A "$WORKFLOW_DIR/output" 2>/dev/null)" ]; then
            mkdir -p "$VAULT_PATH"
            cp -r "$WORKFLOW_DIR/output"/* "$VAULT_PATH/"
            echo "[$(date)] 已同步到 iCloud vault: $VAULT_PATH"
        fi
        echo "[$(date)] 工作流完成"
    else
        echo "[$(date)] 工作流失败，退出码: $EXIT_CODE"
    fi
}

# 主逻辑
if should_run; then
    do_run
fi