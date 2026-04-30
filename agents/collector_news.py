"""
收集 Agent 1: 新闻收集
负责 RSS 订阅 + 主动搜索新闻 + 社交媒体
"""

import feedparser
from datetime import datetime, timedelta, timezone
from typing import Optional
from tools.web_scraper import WebScraper, NewsSearcher
from tools.llm import get_collect_deepseek_flash, get_collect_minimax
from tools.json_parser import parse_json
import logging

logger = logging.getLogger(__name__)


class NewsCollectorAgent:
    """新闻收集 Agent"""

    SYSTEM_PROMPT = """You are a news collection assistant specializing in game research.
Given a list of raw news entries, your task is to:
1. Remove duplicates (same event reported by different sources)
2. Extract core information: title, summary (1-3 sentences), source name, URL, date
3. Assign a category from: academic, industry, technology, culture, events, tools
4. Remove ads and non-news content

Return a JSON array. Each item must have:
- title: string
- summary: string (concise, in the original language)
- source: string (source name)
- url: string
- date: string (YYYY-MM-DD format)
- category: string

IMPORTANT: Return ONLY the JSON array, no explanation, no code blocks."""

    def __init__(self, config: dict, dedup_cache=None):
        self.config = config
        self.dedup_cache = dedup_cache
        self.scraper = WebScraper(
            timeout=config.get("workflow", {}).get("collect", {}).get("timeout_seconds", 30)
        )
        self.searcher = NewsSearcher()
        self.llm, self.model = get_collect_minimax()

    def run(self) -> list[dict]:
        """执行完整的新闻收集流程"""
        all_raw = []

        # 步骤1: RSS 订阅
        logger.info("  [1/4] RSS 订阅源...")
        rss_items = self._collect_rss()
        all_raw.extend(rss_items)
        logger.info(f"        RSS 获取 {len(rss_items)} 条")

        # 步骤2: 主动搜索
        logger.info("  [2/4] 主动搜索新闻...")
        search_items = self._search_news()
        all_raw.extend(search_items)
        logger.info(f"        搜索获取 {len(search_items)} 条")

        # 步骤3: 爬取搜索结果中的网页（深度内容）
        logger.info("  [3/4] 爬取详细内容...")
        enriched = self._enrich_with_content(all_raw)

        # 步骤4: Hacker News 搜索
        logger.info("  [4/4] Hacker News 搜索...")
        hn_items = self._search_hn()
        enriched.extend(hn_items)
        logger.info(f"        HN 获取 {len(hn_items)} 条")

        # 去重和清洗
        cleaned = self._deduplicate(enriched)
        logger.info(f"        去重后 {len(cleaned)} 条")

        return cleaned

    def _collect_rss(self) -> list[dict]:
        """从RSS订阅源收集（通过代理抓取）"""
        feeds = self.config.get("rss_feeds", [])
        max_per_source = self.config.get("workflow", {}).get("collect", {}).get("max_news_per_source", 10)

        all_items = []
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)

        for feed_config in feeds:
            try:
                # 用 scraper 的 session 抓取（支持代理），再传给 feedparser 解析
                resp = self.scraper.session.get(feed_config["url"], timeout=self.scraper.timeout)
                resp.raise_for_status()
                feed = feedparser.parse(resp.text)
                count = 0
                for entry in feed.entries:
                    if count >= max_per_source:
                        break

                    # 解析日期
                    pub_date = self._parse_date(entry)
                    if pub_date and pub_date < cutoff:
                        continue

                    item = {
                        "title": entry.get("title", ""),
                        "summary": entry.get("summary", "")[:500],
                        "source": feed_config.get("name", feed.feed.get("title", "")),
                        "url": entry.get("link", ""),
                        "date": pub_date.strftime("%Y-%m-%d") if pub_date else "",
                        "category": "pending"
                    }

                    # 清理HTML标签
                    item["summary"] = self.scraper._clean_markdown(item["summary"])

                    all_items.append(item)
                    count += 1

            except Exception as e:
                logger.warning(f"        [RSS失败] {feed_config['name']}: {e}")

        return all_items

    def _search_news(self) -> list[dict]:
        """主动搜索新闻"""
        keywords = self.config.get("search_keywords", {})
        all_keywords = keywords.get("en", []) + keywords.get("zh", [])
        max_results = self.config.get("workflow", {}).get("collect", {}).get("search_results_per_keyword", 5)

        # DuckDuckGo 新闻搜索
        results = self.searcher.search_news(all_keywords, max_results=max_results)

        # 转换格式
        items = []
        for r in results:
            items.append({
                "title": r.get("title", ""),
                "summary": r.get("body", "")[:300],
                "source": r.get("source", ""),
                "url": r.get("url", ""),
                "date": r.get("date", "")[:10] if r.get("date") else "",
                "category": "pending",
                "search_keyword": r.get("keyword", "")
            })

        return items

    def _search_hn(self) -> list[dict]:
        """通过 Hacker News Algolia API 搜索游戏相关内容"""
        import requests as req
        import time as t
        from datetime import datetime as dt

        hn_queries = self.config.get("hn_keywords", [
            "game design", "game studies", "game narrative",
            "game development", "video game history", "game AI",
            "interactive storytelling", "ludology"
        ])

        items = []
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)

        for query in hn_queries:
            try:
                url = "https://hn.algolia.com/api/v1/search"
                params = {
                    "query": query,
                    "tags": "story",
                    "hitsPerPage": 3,
                    "numericFilters": "created_at_i>" + str(int(
                        (dt.now(timezone.utc) - timedelta(days=7)).timestamp()
                    ))
                }
                resp = req.get(url, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()

                for hit in data.get("hits", []):
                    pub_date = hit.get("created_at", "")[:10]
                    item = {
                        "title": hit.get("title", ""),
                        "summary": (hit.get("story_text") or "")[:300],
                        "source": f"Hacker News (points: {hit.get('points', 0)}, comments: {hit.get('num_comments', 0)})",
                        "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                        "date": pub_date,
                        "category": "pending"
                    }
                    items.append(item)
                t.sleep(1.5)  # HN API 礼貌延迟
            except Exception as e:
                logger.warning(f"        [HN搜索失败] {query}: {e}")

        return items

    def _enrich_with_content(self, items: list[dict]) -> list[dict]:
        """爬取搜索结果中的网页，获取更详细的内容"""
        # 只爬取摘要太短的条目
        urls_to_fetch = [
            item["url"] for item in items
            if len(item.get("summary", "")) < 100 and item.get("url")
        ]

        if not urls_to_fetch:
            return items

        # 批量爬取
        pages = self.scraper.fetch_batch(urls_to_fetch[:20])  # 限制数量

        # 构建URL到内容的映射
        content_map = {p["url"]: p["html"] for p in pages}

        # 更新摘要
        for item in items:
            html = content_map.get(item["url"])
            if html:
                markdown = self.scraper.html_to_markdown(html)
                # 截取前500字符作为摘要
                item["summary"] = markdown[:500]
                item["full_content"] = markdown

        return items

    def _deduplicate(self, items: list[dict]) -> list[dict]:
        """使用LLM去重和清洗（含跨天去重）"""
        if not items:
            return []

        # 第1层：URL去重（简单去重先执行）
        seen_urls = set()
        url_unique = []
        for item in items:
            url = item.get("url", "")
            if url not in seen_urls:
                seen_urls.add(url)
                url_unique.append(item)

        # 第2层：跨天去重检查
        if self.dedup_cache:
            url_unique, duped = self.dedup_cache.filter_seen(url_unique)
            if duped:
                logger.info(f"        [跨天去重] 过滤 {len(duped)} 条历史重复")

        if len(url_unique) <= 5:
            return url_unique  # 太少不需要LLM去重

        # 第3层：语义相似度去重（数量较多时执行）
        if len(url_unique) > 10:
            url_unique = self._semantic_deduplicate(url_unique)

        # 第4层：LLM 去重和分类
        try:
            input_data = str(url_unique[:100])  # 限制数量避免token溢出
            result = self.llm.chat_json(
                system_prompt=self.SYSTEM_PROMPT,
                user_message=f"Clean and deduplicate these news items:\n{input_data}",
                model=self.model,
                temperature=0.1
            )
            if isinstance(result, list):
                return result
        except Exception as e:
            logger.warning(f"        [LLM清洗失败，使用原始数据]: {e}")

        return url_unique

    def _semantic_deduplicate(self, items: list[dict]) -> list[dict]:
        """使用LLM进行语义相似度去重（同一事件不同来源）"""
        try:
            import re

            comparisons = []
            for item in items:
                title = item.get("title", "")[:300]
                summary = (item.get("summary", "") or "")[:200]
                comparisons.append(f"URL: {item.get('url', '')}\n标题: {title}\n摘要: {summary}")

            result = self.llm.chat_json(
                system_prompt="""You are a deduplication assistant. Given a list of news items,
identify groups that report the SAME event/story from different sources (semantic duplicates).
Return JSON: {"duplicate_urls": ["url1", "url2", ...]} containing URLs to remove (keep the first/best one).
Be conservative - only flag items that are clearly the same story.
IMPORTANT: Return ONLY valid JSON, no code blocks.""",
                user_message="Find semantic duplicates (same story, different sources):\n" + "\n---\n".join(comparisons),
                model=self.model,
                temperature=0.0
            )

            if isinstance(result, dict) and "duplicate_urls" in result:
                dup_urls = set(result["duplicate_urls"])
                if dup_urls:
                    filtered = [item for item in items if item.get("url", "") not in dup_urls]
                    if len(filtered) < len(items):
                        logger.info(f"        [语义去重] 过滤 {len(items) - len(filtered)} 条相似内容")
                    return filtered
        except Exception as e:
            logger.warning(f"        [语义去重失败，跳过]: {e}")

        return items

    @staticmethod
    def _parse_date(entry) -> Optional[datetime]:
        """解析RSS条目的日期"""
        for attr in ["published_parsed", "updated_parsed"]:
            parsed = getattr(entry, attr, None)
            if parsed:
                try:
                    return datetime(*parsed[:6], tzinfo=timezone.utc)
                except Exception:
                    continue
        return None