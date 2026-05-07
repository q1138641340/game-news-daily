"""
OpenCLI Runner — 统一封装 OpenCLI 子进程调用
支持万方、百度学术、CNKI、小红书等数据源
"""

import subprocess
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class OpenCLIRunner:
    """OpenCLI 命令封装，通过 subprocess 调用 opencli"""

    def __init__(self, opencli_path: str = "opencli", timeout: int = 90):
        self.path = opencli_path
        self.timeout = timeout
        self._available: Optional[bool] = None

    def is_available(self) -> bool:
        """检查 OpenCLI 是否可用（daemon + 扩展）"""
        if self._available is not None:
            return self._available

        try:
            result = subprocess.run(
                [self.path, "doctor"],
                capture_output=True, text=True, timeout=10
            )
            # 检查扩展是否连接
            if "Extension: connected" in result.stdout and result.returncode == 0:
                self._available = True
                logger.info("  [OpenCLI] 可用 (扩展已连接)")
            else:
                self._available = False
                logger.warning("  [OpenCLI] 扩展未连接或不可用")
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
            self._available = False
            logger.warning(f"  [OpenCLI] 不可用: {e}")

        return self._available

    def search_wanfang(self, query: str, max_results: int = 5) -> list[dict]:
        """万方学术搜索（公开访问）"""
        return self._search("wanfang", query, max_results, source="万方")

    def search_baidu_scholar(self, query: str, max_results: int = 5) -> list[dict]:
        """百度学术搜索（公开访问）"""
        return self._search("baidu-scholar", query, max_results, source="百度学术")

    def search_cnki(self, query: str, max_results: int = 5) -> list[dict]:
        """CNKI 知网搜索（需登录）"""
        return self._search("cnki", query, max_results, source="知网")

    def search_xiaohongshu(self, query: str, max_results: int = 5) -> list[dict]:
        """小红书关键词搜索（需登录）"""
        return self._search("xiaohongshu", query, max_results, source="小红书")

    def get_xiaohongshu_note(self, url: str) -> Optional[dict]:
        """获取小红书笔记详情（补充正文）"""
        if not self.is_available():
            return None

        try:
            result = subprocess.run(
                [self.path, "xiaohongshu", "note", url, "-f", "json"],
                capture_output=True, text=True, timeout=self.timeout
            )
            if result.returncode != 0:
                return None
            data = json.loads(result.stdout)
            if isinstance(data, dict) and data:
                return {
                    "title": data.get("title", ""),
                    "content": data.get("content", "") or data.get("desc", ""),
                    "likes": data.get("likes", "") or data.get("like_count", ""),
                    "comments": data.get("comments", "") or data.get("comment_count", ""),
                    "author": data.get("author", "") or data.get("user", {}).get("nickname", ""),
                }
        except (json.JSONDecodeError, subprocess.TimeoutExpired, OSError) as e:
            logger.warning(f"  [小红书笔记] 获取失败: {e}")
        return None

    # ---- 内部方法 ----

    def _search(self, adapter: str, query: str, max_results: int, source: str) -> list[dict]:
        """通用搜索方法"""
        if not self.is_available():
            return []

        try:
            result = subprocess.run(
                [self.path, adapter, "search", query,
                 "--limit", str(max_results), "-f", "json"],
                capture_output=True, text=True, timeout=self.timeout
            )
            if result.returncode != 0:
                logger.warning(f"  [{source}] 命令失败: {result.stderr[:100]}")
                return []

            items = self._parse_json_output(result.stdout, source)
            logger.info(f"    [{source}] '{query}': {len(items)} 条")
            return items

        except subprocess.TimeoutExpired:
            logger.warning(f"  [{source}] 超时: '{query}'")
        except OSError as e:
            logger.warning(f"  [{source}] 系统错误: {e}")
        return []

    @staticmethod
    def _parse_json_output(stdout: str, source: str) -> list[dict]:
        """解析 OpenCLI JSON 输出并映射到标准字段"""
        try:
            raw = json.loads(stdout)
        except json.JSONDecodeError:
            return []

        if not isinstance(raw, list):
            return []

        items = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue

            title = (entry.get("title") or "").strip()
            if not title or len(title) < 3:
                continue

            authors = (entry.get("authors") or entry.get("author") or "").strip()
            url = (entry.get("url") or "").strip()

            # 学术来源 → paper 格式
            if source in ("万方", "百度学术", "知网"):
                journal = (entry.get("journal") or entry.get("source") or "").strip()
                year = (entry.get("year") or entry.get("date") or "").strip()
                item = {
                    "title": title,
                    "authors": authors,
                    "abstract": entry.get("abstract", ""),
                    "url": url,
                    "doi": entry.get("doi", ""),
                    "venue": journal,
                    "published_date": year,
                    "category": "chinese-academic",
                    "source": source,
                    "cited": entry.get("cited", ""),
                }
            # 小红书 → news 格式
            else:
                likes = entry.get("likes", "")
                published_at = entry.get("published_at", "")
                author_name = entry.get("author", "")
                item = {
                    "title": title,
                    "summary": "",
                    "source": f"小红书 ({author_name})" if author_name else "小红书",
                    "url": url,
                    "date": published_at[:10] if published_at else "",
                    "category": "social-media",
                    "likes": likes,
                    "author": author_name,
                }

            items.append(item)

        return items
