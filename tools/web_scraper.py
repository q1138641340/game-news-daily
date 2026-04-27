"""
网页爬虫工具
支持普通网页爬取、HTML转Markdown
"""

import re
import requests
from bs4 import BeautifulSoup
from readability import Document
from markdownify import markdownify as md
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin
from typing import Optional
from duckduckgo_search import DDGS
import time


class WebScraper:
    """网页爬虫"""

    def __init__(self, timeout: int = 15, max_workers: int = 5):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            )
        })
        self.timeout = timeout
        self.max_workers = max_workers

    def fetch(self, url: str) -> Optional[dict]:
        """
        爬取单个URL

        Returns:
            {"url": str, "html": str, "status": int, "title": str} 或 None
        """
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or 'utf-8'
            return {
                "url": url,
                "html": resp.text,
                "status": resp.status_code,
                "title": self._extract_title(resp.text)
            }
        except Exception as e:
            print(f"  [爬取失败] {url}: {e}")
            return None

    def fetch_batch(self, urls: list[str]) -> list[dict]:
        """并行爬取多个URL"""
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self.fetch, url): url for url in urls}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)
        return results

    @staticmethod
    def html_to_markdown(html: str) -> str:
        """
        将HTML转为干净的Markdown
        先用readability提取正文，再用markdownify转换

        Args:
            html: 原始HTML

        Returns:
            清洁的Markdown文本
        """
        if not html:
            return ""

        # 1. 用 readability 提取正文（去掉导航、广告、侧边栏等）
        try:
            doc = Document(html)
            content_html = doc.summary()
            title = doc.title()
        except Exception:
            # readability 失败时，降级为原始HTML
            content_html = html
            title = ""

        # 2. 用 markdownify 将HTML转Markdown
        try:
            markdown = md(
                content_html,
                heading_style="ATX",
                bullets="-",
                strip=['img', 'script', 'style', 'noscript', 'iframe'],
                convert=['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                         'ul', 'ol', 'li', 'blockquote', 'a', 'strong', 'em',
                         'code', 'pre', 'table', 'thead', 'tbody', 'tr', 'th', 'td']
            )
        except Exception:
            # markdownify 失败时，用正则清理
            markdown = WebScraper._html_fallback(content_html)

        # 3. 后处理清理
        markdown = WebScraper._clean_markdown(markdown)

        # 4. 加上标题
        if title:
            markdown = f"# {title}\n\n{markdown}"

        return markdown

    @staticmethod
    def _html_fallback(html: str) -> str:
        """HTML清理的降级方案（纯正则）"""
        text = html
        # 移除脚本和样式
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        # 移除所有HTML标签
        text = re.sub(r'<[^>]+>', ' ', text)
        # 合并空白
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    @staticmethod
    def _clean_markdown(text: str) -> str:
        """清理Markdown文本"""
        # 移除多余空行（保留段落分隔）
        text = re.sub(r'\n{3,}', '\n\n', text)
        # 移除行尾空格
        text = re.sub(r'[ \t]+\n', '\n', text)
        # 移除连续的空链接
        text = re.sub(r'\[([^\]]*)\]\(\s*\)', r'\1', text)
        return text.strip()

    @staticmethod
    def _extract_title(html: str) -> str:
        """从HTML中提取标题"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            if soup.title and soup.title.string:
                return soup.title.string.strip()
            h1 = soup.find('h1')
            if h1:
                return h1.get_text(strip=True)
        except Exception:
            pass
        return ""

    @staticmethod
    def extract_links(html: str, base_url: str, pattern: str = "") -> list[str]:
        """从页面提取链接"""
        soup = BeautifulSoup(html, 'html.parser')
        links = []
        for a in soup.find_all('a', href=True):
            href = urljoin(base_url, a['href'])
            if href.startswith('http') and (not pattern or pattern in href):
                links.append(href)
        return list(set(links))


class NewsSearcher:
    """新闻搜索（Google News RSS，通过代理稳定抓取）"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            )
        })

    def search_news(self, keywords: list[str], max_results: int = 5) -> list[dict]:
        """
        通过 Google News RSS 搜索新闻（通过代理抓取）

        Args:
            keywords: 关键词列表
            max_results: 每个关键词的最大结果数

        Returns:
            新闻列表
        """
        import feedparser
        import urllib.parse

        all_results = []

        for keyword in keywords:
            try:
                encoded = urllib.parse.quote(keyword)
                # Google News RSS 搜索（免费，无需API key）
                url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"

                if any('\u4e00' <= c <= '\u9fff' for c in keyword):
                    # 中文关键词用中文版
                    url = f"https://news.google.com/rss/search?q={encoded}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"

                # 用 requests 抓取（支持代理），再传给 feedparser 解析
                resp = self.session.get(url, timeout=15)
                resp.raise_for_status()
                feed = feedparser.parse(resp.text)

                count = 0
                for entry in feed.entries:
                    if count >= max_results:
                        break

                    all_results.append({
                        "keyword": keyword,
                        "title": entry.get("title", ""),
                        "url": entry.get("link", ""),
                        "date": entry.get("published", "")[:10] if entry.get("published") else "",
                        "source": entry.get("source", {}).get("title", "") if isinstance(entry.get("source"), dict) else str(entry.get("source", "")),
                        "body": entry.get("summary", "")[:500]
                    })
                    count += 1

                if count > 0:
                    print(f"    [Google News] '{keyword}': {count} 条")

                time.sleep(1)  # 礼貌延迟

            except Exception as e:
                print(f"  [搜索失败] '{keyword}': {str(e)[:80]}")

        # 去重（按URL）
        seen = set()
        unique = []
        for item in all_results:
            url = item["url"]
            if url not in seen:
                seen.add(url)
                unique.append(item)

        return unique

    def search_web(self, keywords: list[str], max_results: int = 5) -> list[dict]:
        """
        搜索网页（DuckDuckGo 文本搜索，带重试）
        """
        all_results = []
        for i, keyword in enumerate(keywords):
            if i > 0:
                time.sleep(4)

            for attempt in range(2):  # 减少重试次数
                try:
                    with DDGS() as ddgs:
                        results = list(ddgs.text(
                            keywords=keyword,
                            max_results=max_results
                        ))
                    for r in results:
                        all_results.append({
                            "keyword": keyword,
                            "title": r.get("title", ""),
                            "url": r.get("href", r.get("link", "")),
                            "body": r.get("body", "")[:500]
                        })
                    break
                except Exception as e:
                    if attempt == 0:
                        time.sleep(8)
                    else:
                        print(f"  [网页搜索失败] '{keyword}': {str(e)[:60]}")

        # 去重
        seen = set()
        unique = []
        for item in all_results:
            url = item["url"]
            if url not in seen:
                seen.add(url)
                unique.append(item)

        return unique
