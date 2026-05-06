# CLAUDE.md — Daily News Workflow

游戏研究日报自动生成项目。多 Agent 流水线，105 RSS 源 → 4 层去重 → 双重审查 → Markdown 日报。

## 架构

```
Phase 0: 跨天去重 (DedupCache, 90天)
Phase 1: 信息收集 (NewsCollector + AcademicCollector, MiniMax M2.7 清洗)
Phase 2: 预处理 (Preprocessor, DeepSeek Flash)
Phase 3: 质量审查 (QualityReviewer, Kimi 2.5 + 幻觉检测)
Phase 4: 相关性审查 (RelevanceReviewer, Kimi 2.5)
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
- 质量审查: Kimi 2.5 / moonshot-v1-32k
- 相关性审查: Kimi 2.5
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

## 环境变量

- `KIMI_API_KEY` / `KIMI_BASE_URL` — 审查阶段
- `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` — 生成阶段
- `MINIMAX_API_KEY` / `MINIMAX_BASE_URL` — 收集阶段
- `OBSIDIAN_VAULT_PATH` — 输出路径 (GitHub Actions 模式可选)

## 定时运行

GitHub Actions: `UTC 18:30 = 北京时间 02:30`

## 维护提醒

- 微博 SUB cookie 有效期约 3-6 月，下次更新: 2026-08 前
- 4 个学术 RSS 源可能失效 (Game Studies/DiGRA/SAGE)，不影响整体运行
- 小红书和 Facebook 目前不可行 (无公开 API)

## 常见操作

加微博账号: config.yaml → `https://weibo-rss-bridge.vercel.app/api/weibo/user/{UID}`

加 X 账号: config.yaml → `https://nitter.net/{handle}/rss`

测试微博 UID: `curl -s "https://weibo.com/ajax/statuses/mymblog?uid={UID}" -H "Cookie: SUB=..."`
