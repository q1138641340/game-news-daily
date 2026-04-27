#!/bin/bash
# Obsidian Git 同步脚本
# 将此脚本放在 Obsidian vault 的 .obsidian/scripts/ 目录下
# 并在 Obsidian Git 插件中配置为自定义命令

set -e

# 获取 vault 路径
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VAULT_PATH="$(cd "$SCRIPT_DIR/../.." && pwd)"
RESEARCH_FEED_DIR="$VAULT_PATH/Research Feed"

# GitHub 仓库配置（需要修改为你的仓库）
GITHUB_REPO="${GITHUB_REPO:-sunjinghe/daily-news-workflow}"
BRANCH="daily-reports"

echo "=== Daily Report Sync ==="
echo "Vault path: $VAULT_PATH"
echo "Research Feed: $RESEARCH_FEED_DIR"
echo "GitHub Repo: $GITHUB_REPO"
echo ""

# 创建 Research Feed 目录
mkdir -p "$RESEARCH_FEED_DIR"

# 临时目录用于拉取最新报告
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

echo "[1/4] Fetching latest daily reports..."

# 使用 git archive 获取最新报告（不需要完整克隆）
if command -v git >/dev/null 2>&1; then
    # 方法1: 如果 vault 是 git 仓库，使用 git fetch
    if [ -d "$VAULT_PATH/.git" ]; then
        cd "$VAULT_PATH"

        # 检查远程仓库是否已配置
        if ! git remote get-url origin >/dev/null 2>&1; then
            echo "Adding remote origin..."
            git remote add origin "https://github.com/$GITHUB_REPO.git" 2>/dev/null || true
        fi

        # 获取 daily-reports 分支的最新内容
        git fetch origin "$BRANCH" 2>/dev/null || {
            echo "Warning: Could not fetch from remote. Using local files."
            exit 0
        }

        # 检出 output 目录
        git checkout origin/$BRANCH -- output/ 2>/dev/null || {
            echo "No output directory found in $BRANCH branch"
            exit 0
        }

        # 复制到 Research Feed
        if [ -d "$VAULT_PATH/output" ]; then
            echo "[2/4] Copying reports to Research Feed..."
            cp -r "$VAULT_PATH/output/"* "$RESEARCH_FEED_DIR/" 2>/dev/null || true

            echo "[3/4] Cleaning up..."
            rm -rf "$VAULT_PATH/output"

            echo "[4/4] Committing changes..."
            git add "Research Feed/"
            if ! git diff --staged --quiet; then
                git commit -m "Sync daily reports $(date +%Y-%m-%d)" || true
            fi
        fi
    else
        # 方法2: 下载 ZIP 归档
        echo "Vault is not a git repo. Downloading ZIP archive..."
        ZIP_URL="https://github.com/$GITHUB_REPO/archive/refs/heads/$BRANCH.zip"

        if command -v curl >/dev/null 2>&1; then
            curl -L -o "$TEMP_DIR/daily-reports.zip" "$ZIP_URL" 2>/dev/null || {
                echo "Error: Could not download from GitHub"
                exit 1
            }
        elif command -v wget >/dev/null 2>&1; then
            wget -O "$TEMP_DIR/daily-reports.zip" "$ZIP_URL" 2>/dev/null || {
                echo "Error: Could not download from GitHub"
                exit 1
            }
        else
            echo "Error: curl or wget required"
            exit 1
        fi

        # 解压
        if command -v unzip >/dev/null 2>&1; then
            unzip -q "$TEMP_DIR/daily-reports.zip" -d "$TEMP_DIR"
            EXTRACTED_DIR="$TEMP_DIR/daily-news-workflow-$BRANCH"

            if [ -d "$EXTRACTED_DIR/output" ]; then
                echo "[2/4] Copying reports to Research Feed..."
                cp -r "$EXTRACTED_DIR/output/"* "$RESEARCH_FEED_DIR/" 2>/dev/null || true
            fi
        fi
    fi
else
    echo "Error: git is not installed"
    exit 1
fi

echo ""
echo "=== Sync Complete ==="
echo "Reports synced to: $RESEARCH_FEED_DIR"
ls -la "$RESEARCH_FEED_DIR" 2>/dev/null || true
