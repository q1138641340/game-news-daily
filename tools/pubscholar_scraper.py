"""
PubScholar 网页爬虫
支持从 pubscholar.cn 抓取学术论文元数据

注意：PubScholar 有严格的反爬机制，包括动态生成的请求头
(nonce, timestamp, signature, x-finger)。
主要通过 HTML 解析获取数据。
"""

import requests
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class PubScholarScraper:
    """PubScholar 爬虫"""

    BASE_URL = "https://pubscholar.cn"
    SEARCH_URL = "https://pubscholar.cn/search"

    def __init__(self, timeout: int = 30):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })

    def search(self, query: str, max_results: int = 10) -> list[dict]:
        """
        搜索 PubScholar

        Args:
            query: 搜索关键词
            max_results: 最大结果数

        Returns:
            list[dict]: 论文列表
        """
        try:
            return self._search_via_html(query, max_results)
        except Exception as e:
            logger.warning(f"        [PubScholar爬取失败] {e}")
            return []

    def _search_via_html(self, query: str, max_results: int) -> list[dict]:
        """通过解析 HTML 搜索结果页面获取论文"""
        try:
            # 编码搜索词
            encoded_query = requests.utils.quote(query)
            url = f"{self.SEARCH_URL}?q={encoded_query}"

            resp = self.session.get(url, timeout=30)

            if resp.status_code != 200:
                logger.warning(f"        [PubScholar HTTP错误] {resp.status_code}")
                return []

            return self._parse_html_results(resp.text, max_results)

        except requests.exceptions.Timeout:
            logger.warning(f"        [PubScholar超时]")
            return []
        except Exception as e:
            logger.warning(f"        [PubScholar请求失败] {str(e)[:60]}")
            return []

    def _parse_html_results(self, html: str, max_results: int) -> list[dict]:
        """解析 HTML 中的论文条目"""
        papers = []

        # 尝试多种可能的 HTML 结构模式

        # 模式1: 通用论文条目 div
        item_patterns = [
            r'<div[^>]*class="[^"]*(?:result|item|paper|article)[^"]*"[^>]*>(.*?)</div>',
            r'<li[^>]*class="[^"]*(?:result|item|paper|article)[^"]*"[^>]*>(.*?)</li>',
            r'<article[^>]*>(.*?)</article>',
        ]

        # 模式2: 标题-链接组合
        title_patterns = [
            r'<h[23][^>]*><a[^>]*href="([^"]+)"[^>]*>([^<]+)</a></h[23]>',
            r'<h[23][^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</h[23]>',
            r"title[\"\s]*:[\"\s]*[\"']([^\"']+)[\"']",
        ]

        # 模式3: DOI 提取
        doi_pattern = r'(10\.\d{4,}/[^\s<>"{}|\\^`\[\]]+)'

        # 模式4: 日期提取
        date_pattern = r'(\d{4}[-年]?\d{0,2}[-月]?\d{0,2})'

        # 模式5: 作者提取
        author_patterns = [
            r'作者[:：]\s*([^<\n]+)',
            r'author[s]?[:：]\s*([^<\n]+)',
            r'class="[^"]*author[^"]*"[^>]*>([^<]+)</[^>]+>',
        ]

        # 简单启发式：从 HTML 中提取可能的论文信息
        # 由于 PubScholar 是 SPA，内容可能嵌入在 JS 中

        # 尝试提取嵌入的 JSON 数据
        json_pattern = r'<script[^>]*type="application/json"[^>]*>([^<]+)</script>'
        json_matches = re.findall(json_pattern, html, re.DOTALL)

        for json_str in json_matches:
            try:
                import json
                data = json.loads(json_str)
                if isinstance(data, dict):
                    # 尝试在 JSON 中找论文数据
                    papers.extend(self._extract_from_json(data, max_results))
            except:
                pass

        # 如果没有找到 JSON 数据，尝试启发式提取
        if not papers:
            papers.extend(self._heuristic_extract(html, max_results))

        return papers[:max_results]

    def _extract_from_json(self, data: dict, max_results: int) -> list[dict]:
        """从 JSON 数据中提取论文信息"""
        papers = []

        def recursive_search(obj, depth=0):
            if depth > 5 or not obj:
                return

            if isinstance(obj, dict):
                # 检查是否像论文数据
                if 'title' in obj and ('url' in obj or 'doi' in obj or 'link' in obj):
                    papers.append({
                        "title": str(obj.get('title', '')),
                        "authors": str(obj.get('authors', obj.get('author', ''))),
                        "abstract": str(obj.get('abstract', obj.get('description', '')))[:500],
                        "url": obj.get('url', obj.get('link', obj.get('doi', ''))),
                        "doi": obj.get('doi', ''),
                        "pdf_url": obj.get('pdf', obj.get('pdf_url', '')),
                        "venue": obj.get('venue', obj.get('journal', obj.get('source', 'PubScholar'))),
                        "published_date": obj.get('date', obj.get('published', obj.get('publish_date', ''))),
                    })

                for v in obj.values():
                    recursive_search(v, depth + 1)

            elif isinstance(obj, list):
                for item in obj:
                    recursive_search(item, depth + 1)

        recursive_search(data)
        return papers

    def _heuristic_extract(self, html: str, max_results: int) -> list[dict]:
        """启发式提取论文信息（备选方案）"""
        papers = []

        # DOI 提取
        dois = re.findall(r'10\.\d{4,}/[^\s<>"{}|\\^`\[\]]+', html)

        # 尝试提取可能的标题（通常是 h2, h3 中的长文本）
        title_matches = re.findall(r'<h[23][^>]*>([^<]{10,200})</h[23]>', html)

        # 尝试提取链接
        links = re.findall(r'href="(/article/[^"]+)"', html)

        for i, title in enumerate(title_matches[:max_results]):
            if len(title) < 10:
                continue

            paper = {
                "title": title.strip(),
                "authors": "",
                "abstract": "",
                "url": "",
                "doi": dois[i] if i < len(dois) else "",
                "pdf_url": "",
                "venue": "PubScholar",
                "published_date": "",
            }

            if i < len(links):
                paper["url"] = self.BASE_URL + links[i] if links[i].startswith('/') else links[i]

            papers.append(paper)

        return papers
