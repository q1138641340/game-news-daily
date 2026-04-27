# Daily News Workflow

一个自动化游戏研究日报生成工具，每天自动收集游戏研究、叙事学、媒介理论等领域的最新学术论文和行业新闻。

## 功能特点

- **自动收集**: 从 arXiv、Semantic Scholar、CrossRef、RSS 订阅源等收集内容
- **智能过滤**: 使用 LLM 进行质量审查和相关性评估
- **日报生成**: 自动生成格式化的 Markdown 日报
- **PDF 下载**: 自动下载开放获取的论文 PDF
- **定时运行**: 支持 GitHub Actions 每天早上 8 点自动运行

## 快速开始

### 本地运行

1. 安装依赖:
```bash
pip install -r requirements.txt
```

2. 配置环境变量 (`.env`):
```bash
DEEPSEEK_API_KEY=your_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
KIMI_API_KEY=your_key
KIMI_BASE_URL=https://api.moonshot.cn/v1
MINIMAX_API_KEY=your_key
MINIMAX_BASE_URL=https://api.minimaxi.com/v1
```

3. 运行:
```bash
python main.py
```

### GitHub Actions 自动运行

本项目已配置 GitHub Actions，每天早上 8 点（北京时间）自动运行:

1. Fork 本仓库
2. 在仓库 Settings -> Secrets and variables -> Actions 中添加以下 secrets:
   - `DEEPSEEK_API_KEY`
   - `DEEPSEEK_BASE_URL`
   - `KIMI_API_KEY`
   - `KIMI_BASE_URL`
   - `MINIMAX_API_KEY`
   - `MINIMAX_BASE_URL`

3. 工作流会自动运行，生成的日报会推送到 `daily-reports` 分支的 `output/` 目录

## Obsidian 同步

### 方案 1: Obsidian Git 插件 (推荐)

1. 在 Obsidian 中安装 [Obsidian Git](https://github.com/denolehov/obsidian-git) 插件

2. 在 Obsidian vault 中初始化 Git 仓库:
```bash
cd "你的 Obsidian Vault 路径"
git init
git remote add origin https://github.com/你的用户名/daily-news-workflow.git
```

3. 配置 Obsidian Git 插件:
   - 打开设置 -> Obsidian Git
   - 设置自动备份间隔（例如每 30 分钟）
   - 启用 "Auto pull on startup"

4. 创建同步脚本 `.obsidian/scripts/sync-daily-report.sh`:
```bash
#!/bin/bash
VAULT_PATH="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$VAULT_PATH"

# 拉取最新的日报
git fetch origin
git checkout daily-reports -- output/ 2>/dev/null || true

# 复制到 Research Feed 目录
if [ -d "output" ]; then
    mkdir -p "Research Feed"
    cp -r output/* "Research Feed/" 2>/dev/null || true
    echo "Synced daily reports"
fi
```

5. 在 Obsidian Git 插件设置中添加自定义命令:
   - Command: `bash .obsidian/scripts/sync-daily-report.sh`
   - 设置定时执行或手动触发

### 方案 2: 手动同步

1. 克隆仓库的 daily-reports 分支:
```bash
git clone -b daily-reports https://github.com/你的用户名/daily-news-workflow.git
```

2. 将 `output/` 目录复制到你的 Obsidian vault:
```bash
cp -r daily-news-workflow/output/* "你的 Obsidian Vault/Research Feed/"
```

### 方案 3: 使用 Git Submodule

1. 在 Obsidian vault 中添加 submodule:
```bash
cd "你的 Obsidian Vault"
git submodule add -b daily-reports https://github.com/你的用户名/daily-news-workflow.git daily-news-workflow
```

2. 创建软链接:
```bash
ln -s daily-news-workflow/output Research\ Feed
```

3. 更新时:
```bash
git submodule update --remote
```

## 目录结构

```
.
├── agents/                 # 各个 Agent 模块
│   ├── collector_news.py   # 新闻收集
│   ├── collector_academic.py # 学术论文收集
│   ├── preprocessor.py     # 内容预处理
│   ├── reviewer_quality.py # 质量审查
│   ├── reviewer_relevance.py # 相关性审查
│   └── formatter.py        # 日报格式化
├── tools/                  # 工具模块
│   ├── web_scraper.py      # 网页爬虫
│   ├── pdf_downloader.py   # PDF 下载
│   ├── obsidian.py         # Obsidian 写入
│   └── llm.py              # LLM 客户端
├── .github/workflows/      # GitHub Actions 配置
│   └── daily.yml           # 定时工作流
├── config.yaml            # 配置文件
├── requirements.txt       # Python 依赖
└── main.py               # 主入口
```

## 配置说明

编辑 `config.yaml` 来自定义:

- `search_keywords`: 新闻搜索关键词
- `academic_keywords`: 学术论文搜索关键词
- `rss_feeds`: RSS 订阅源
- `workflow`: 工作流参数（收集数量、审查阈值等）
- `obsidian`: Obsidian vault 路径和输出文件夹

## 许可证

MIT
