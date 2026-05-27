# CLAUDE.md — Daily News Workflow

游戏研究日报自动生成项目。Mac + Win + GitHub Actions 三端协同，105+ RSS 源 → 4 层去重 → 双重审查 → Markdown 日报。

## 协同架构

```
GitHub (q1138641340/game-news-daily) ← 中转站
  │
  ├── 02:30 BJT  GH Actions → git pull → 读 Win pending.json
  │       → 105 RSS + API + LLM审查 → 生成日报 → push vault
  │
  ├── 06:00 BJT  Win → OpenCLI(万方/百度学术/小红书)
  │       → 存 output/.cache/opencli-pending.json → git push
  │
  └── Mac (按需) → bash run-sync.sh  原型验证
```

**时间关系**：GH Actions 生成昨天日报。Win 06:00 数据 → 第二天 GH 02:30 拉取审查。

**两端分工：**
| | Mac | Win |
|---|-----|-----|
| 角色 | 代码开发、原型验证 | OpenCLI 采集 |
| 采集内容 | 按需 | 万方 + 百度学术 + 小红书 |
| 时长 | — | ~5 分钟 |
| 依赖 | 无 | Chrome + OpenCLI 扩展 |
| 脚本 | `run-sync.sh` | `run-win-opencli.py` |

## 流水线架构

```
Phase 0: 跨天去重 (DedupCache, 90天)
Phase 1: 信息收集 (NewsCollector + AcademicCollector, MiniMax M2.7 清洗)
Phase 2: 预处理 (Preprocessor, DeepSeek Flash)
Phase 3: 质量审查 (QualityReviewer, MiniMax M2.7 + 幻觉检测)
Phase 4: 相关性审查 (RelevanceReviewer, MiniMax M2.7)
Phase 5: 格式化输出 (Formatter, DeepSeek V4 Pro + 工序证明)
Phase 6: 保存 + 标记去重缓存
```

## 关键文件

| 文件 | 职责 |
|------|------|
| `main.py` | 主入口，串联所有 Phase |
| `agents/collector_news.py` | RSS + 搜索 + 爬取新闻 |
| `agents/collector_academic.py` | arXiv/Semantic Scholar/CrossRef/DBLP |
| `agents/preprocessor.py` | LLM 正文提取去噪 |
| `agents/reviewer_quality.py` | 质量评分 + 幻觉检测 |
| `agents/reviewer_relevance.py` | 领域相关性评分 |
| `agents/formatter.py` | LLM 生成日报 + 工序证明 |
| `tools/dedup_cache.py` | 跨天去重缓存 (seen_items.json) |
| `tools/llm.py` | LLM 客户端 (MiniMax/DeepSeek/Kimi) |
| `config.yaml` | 配置 (105 RSS + 搜索关键词 + 参数) |

## 模型选择

- 收集/清洗: MiniMax M2.7-highspeed (快速便宜)
- 预处理: DeepSeek Flash (备用)
- 质量审查: MiniMax M2.7-highspeed
- 相关性审查: MiniMax M2.7-highspeed
- 日报生成: DeepSeek V4 Pro
- 战略增强: DeepSeek V4 Pro

## 去重机制 (4 层)

1. URL 精确去重 (URL 归一化: 去参数/www/http→https/twitter↔x.com)
2. 跨天缓存去重 (90天, seen_items.json)
3. LLM 语义去重 (collector_news.py)
4. Jaccard 标题去重 (formatter.py, >85%)

## 自建桥接服务

| 服务 | URL | 用途 | Cookie |
|------|-----|------|--------|
| Weibo RSS Bridge | weibo-rss-bridge.vercel.app | 微博→RSS | SUB (2026-05-06 设置) |
| Nitter | nitter.net | X/Twitter→RSS | 无需 |

## OpenCLI 集成（需 Chrome 扩展，仅 Win 端）

| 源 | 命令 | 访问级别 |
|---|------|---------|
| 万方 | `opencli wanfang search` | 公开 |
| 百度学术 | `opencli baidu-scholar search` | 公开 |
| 小红书 | `opencli xiaohongshu search` | 需登录 |
| CNKI | `opencli cnki search` | 验证码堵死 |

封装于 `tools/opencli_runner.py`，fail-open 设计。

## 协同脚本

| 脚本 | 平台 | 用途 |
|------|------|------|
| `run-sync.sh` | Mac | git pull → [采集] → git push |
| `run-win-opencli.py` | Win | OpenCLI采集 → 存 pending.json → git push |
| `run-local.sh` | Mac | 旧版本地脚本（输出到 iCloud vault） |

## 环境变量

- `KIMI_API_KEY` / `KIMI_BASE_URL` — 审查阶段
- `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` — 生成阶段
- `MINIMAX_API_KEY` / `MINIMAX_BASE_URL` — 收集阶段
- `OBSIDIAN_VAULT_PATH` — 输出路径 (GitHub Actions 模式可选)

## 定时运行

| 时间 (BJT) | 平台 | 采集内容 |
|-----------|------|---------|
| 02:30 | GitHub Actions | 105 RSS + API + 读 Win pending.json + LLM审查 |
| 06:00 | Win Task Scheduler | OpenCLI(万方/百度学术/小红书) → pending.json |

Mac 端按需运行 `bash run-sync.sh`。

## 维护提醒

- 微博 SUB cookie 有效期约 3-6 月，下次更新: 2026-08 前
- 4 个学术 RSS 源已废弃 (Game Studies/DiGRA/SAGE)，已改用 CrossRef ISSN 直搜替代（见 config.yaml academic_journals）
- Facebook 不可行 (需 Meta Developer App)
- CNKI 知网被验证码堵死，用万方+百度学术替代
- OpenCLI Chrome 扩展需保持连接（Win 端）

## 常见操作

加微博账号: config.yaml → `https://weibo-rss-bridge.vercel.app/api/weibo/user/{UID}`

加 X 账号: config.yaml → `https://nitter.net/{handle}/rss`

测试微博 UID: `curl -s "https://weibo.com/ajax/statuses/mymblog?uid={UID}" -H "Cookie: SUB=..."`
