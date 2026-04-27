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

    def __init__(self, config: dict):
        self.config = config
        self.scraper = WebScraper(
            timeout=config.get("workflow", {}).get("collect", {}).get("timeout_seconds", 30)
        )
        self.searcher = NewsSearcher()
        self.llm, self.model = get_collect_minimax()  # MiniMax 收集

    def run(self) -> list[dict]:
        """执行完整的新闻收集流程"""
        all_raw = []

        # 步骤1: RSS 订阅
        print("  [1/3] RSS 订阅源...")
        rss_items = self._collect_rss()
        all_raw.extend(rss_items)
        print(f"        RSS 获取 {len(rss_items)} 条")

        # 步骤2: 主动搜索
        print("  [2/3] 主动搜索新闻...")
        search_items = self._search_news()
        all_raw.extend(search_items)
        print(f"        搜索获取 {len(search_items)} 条")

        # 步骤3: 爬取搜索结果中的网页（深度内容）
        print("  [3/3] 爬取详细内容...")
        enriched = self._enrich_with_content(all_raw)

        # 去重和清洗
        cleaned = self._deduplicate(enriched)
        print(f"        去重后 {len(cleaned)} 条")

        return cleaned

    def _collect_rss(self) -> list[dict]:
        """从RSS订阅源收集"""
        feeds = self.config.get("rss_feeds", [])
        max_per_source = self.config.get("workflow", {}).get("collect", {}).get("max_news_per_source", 10)

        all_items = []
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)

        for feed_config in feeds:
            try:
                feed = feedparser.parse(feed_config["url"])
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
                print(f"        [RSS失败] {feed_config['name']}: {e}")

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
        """使用LLM去重和清洗"""
        if not items:
            return []

        # URL去重（简单去重先执行）
        seen_urls = set()
        url_unique = []
        for item in items:
            url = item.get("url", "")
            if url not in seen_urls:
                seen_urls.add(url)
                url_unique.append(item)

        if len(url_unique) <= 5:
            return url_unique  # 太少不需要LLM去重

        # LLM 去重和分类
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
            print(f"        [LLM清洗失败，使用原始数据]: {e}")

        return url_unique

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