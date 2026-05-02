# Daily News Workflow

一个自动化游戏研究日报生成工具，每天自动收集游戏研究、叙事学、媒介理论等领域的最新学术论文和行业新闻。

## 功能特点

- **自动收集**: 从 arXiv、Semantic Scholar、CrossRef、RSS 订阅源等收集内容
- **智能过滤**: 使用 LLM 进行质量审查和相关性评估
- **日报生成**: 自动生成格式化的 Markdown 日报
- **PDF 下载**: 自动下载开放获取的论文 PDF
- **反幻觉检测**: 质量审查中集成 AI 幻觉检测（DOI验证、作者真实性、标题自然度检查）
- **跨天去重**: 90天缓存 + URL归一化（去追踪参数/去www/统一协议），缓存标记在LLM转换前执行防止键失效
- **安全审查**: 质量/相关性审查采用 fail-closed 策略，LLM解析失败时默认拒绝
- **战略增强**: 日报末尾自动追加核心张力声明、趋势反向思考、本周研究路径
- **定时运行**: 支持 GitHub Actions 每天凌晨 2:30（北京时间）自动运行

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

本项目已配置 GitHub Actions，每天凌晨 2:30（北京时间）自动运行:

1. Fork 本仓库
2. 在仓库 Settings -> Secrets and variables -> Actions 中添加以下 secrets:
   - `DEEPSEEK_API_KEY`
   - `DEEPSEEK_BASE_URL`
   - `KIMI_API_KEY`
   - `KIMI_BASE_URL`
   - `MINIMAX_API_KEY`
   - `MINIMAX_BASE_URL`
   - `GH_PAT` (Personal Access Token，需有 github-obsidian-vault 仓库访问权限)

3. 工作流会自动运行，生成的日报会推送到 `github-obsidian-vault` 仓库的 `Research Feed/` 目录

## Obsidian 同步

日报通过 GitHub Actions 自动同步到 `github-obsidian-vault` 仓库。

在 Obsidian vault 中配置:

1. 安装 [Obsidian Git](https://github.com/denolehov/obsidian-git) 插件

2. 克隆同步仓库:
```bash
git clone https://github.com/sunjinghe/github-obsidian-vault.git "你的 Obsidian Vault"
```

3. 配置 Obsidian Git 插件:
   - 设置自动备份间隔（例如每 30 分钟）
   - 启用 "Auto pull on startup"

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
│   ├── dedup_cache.py      # 跨天去重缓存
│   └── llm.py              # LLM 客户端
├── .github/workflows/      # GitHub Actions 配置
│   └── daily.yml           # 定时工作流
├── config.yaml            # 配置文件
├── requirements.txt       # Python 依赖
└── main.py               # 主入口
```

## 输出结构

Workflow 运行后，日报输出到 `github-obsidian-vault/Research Feed/` 目录：

```
Research Feed/
└── YYYY-MM-DD/           ← 日期文件夹
    ├── Daily-Report.md   ← 日报内容
    └── Papers/           ← 论文 PDF
        ├── paper1.pdf
        └── paper2.pdf
```

## 配置说明

编辑 `config.yaml` 来自定义:

- `search_keywords`: 新闻搜索关键词
- `academic_keywords`: 学术论文搜索关键词
- `rss_feeds`: RSS 订阅源（含学术期刊、游戏媒体、行业来源、Reddit 社交媒体）
- `hn_keywords`: Hacker News 搜索关键词
- `workflow`: 工作流参数（收集数量、审查阈值等）
- `obsidian`: Obsidian vault 路径和输出文件夹

## 许可证

MIT
