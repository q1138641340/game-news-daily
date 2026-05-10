"""
引用追踪器
从日报中提取和追踪引用，生成参考文献表
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class CitationTracker:
    """
    从日报中提取和追踪引用
    支持从 Markdown 格式的日报中解析参考文献
    """

    def __init__(self):
        self.references = []

    def extract_references(self, daily_reports: list[dict]) -> list[dict]:
        """
        从多日日报中提取参考文献

        Args:
            daily_reports: 过去7天的日报内容列表，每项包含：
                - date: str
                - content: str (完整日报 Markdown)
                - academic_papers: list[dict]
                - industry_news: list[dict]

        Returns:
            list[dict]: 参考文献列表
            {
                "id": 1,
                "type": "paper|news|report",
                "title": str,
                "authors": str,
                "source": str,
                "url": str,
                "date": str,
                "venue": str
            }
        """
        refs = []
        seen_titles = set()

        for report in daily_reports:
            date = report.get("date", "")

            # 从学术论文中提取
            for paper in report.get("academic_papers", []):
                ref = self._extract_paper_ref(paper, date)
                if ref and ref["title"] not in seen_titles:
                    ref["id"] = len(refs) + 1
                    refs.append(ref)
                    seen_titles.add(ref["title"])

            # 从行业新闻中提取
            for news in report.get("industry_news", []):
                ref = self._extract_news_ref(news, date)
                if ref and ref["title"] not in seen_titles:
                    ref["id"] = len(refs) + 1
                    refs.append(ref)
                    seen_titles.add(ref["title"])

        self.references = refs
        logger.info(f"  [引用追踪] 共提取 {len(refs)} 条参考文献")
        return refs

    def _extract_paper_ref(self, paper: dict, date: str) -> Optional[dict]:
        """从论文字典中提取引用信息"""
        title = paper.get("title", "")
        if not title:
            return None

        return {
            "type": "paper",
            "title": title,
            "authors": paper.get("authors", ""),
            "source": paper.get("venue", "arXiv"),
            "url": paper.get("url", ""),
            "doi": paper.get("doi", ""),
            "date": paper.get("published_date", date),
            "venue": paper.get("venue", "")
        }

    def _extract_news_ref(self, news: dict, date: str) -> Optional[dict]:
        """从新闻字典中提取引用信息"""
        title = news.get("title", "")
        if not title:
            return None

        return {
            "type": "news",
            "title": title,
            "authors": news.get("author", ""),
            "source": news.get("source", ""),
            "url": news.get("url", ""),
            "date": date,
            "venue": news.get("source", "")
        }

    def extract_from_markdown(self, markdown_text: str, date: str) -> list[dict]:
        """
        从 Markdown 文本中直接提取参考文献（用于直接解析日报文件）

        Args:
            markdown_text: 日报 Markdown 内容
            date: 日报日期

        Returns:
            list[dict]: 参考文献列表
        """
        refs = []
        seen_titles = set()

        # 提取学术论文部分
        # 格式1: #### 论文标题  (h4)  + **作者**: ... **来源**: ... **DOI/PDF**: ...
        # 格式2: **论文标题** (bold) + **作者**: ... **来源**: ... **DOI**: ...
        paper_patterns = [
            # h4 标题格式
            r'####\s+([^\n]+)\s*\n(?:.*?\n)*?\s*\*\*作者\*\*:\s*([^\n]+)?\s*\n\s*\*\*来源\*\*:\s*([^\n]+)',
            # bold 标题格式
            r'\*\*([^*]+)\*\*\s*\n\s*\*\*作者\*\*:\s*([^\n]+)?\s*\n\s*\*\*来源\*\*:\s*([^\n]+)',
        ]

        for pattern in paper_patterns:
            for match in re.finditer(pattern, markdown_text, re.MULTILINE):
                title = match.group(1).strip()
                authors = match.group(2).strip() if match.group(2) else ""
                source = match.group(3).strip()

                # 提取 DOI（可选）
                doi = ""
                doi_match = re.search(r'\*\*DOI(?:/PDF)?\*\*:\s*([^\n]+)', markdown_text[match.start():match.end()+500])
                if doi_match:
                    doi = doi_match.group(1).strip()

                if title and title not in seen_titles and not title.startswith('#'):
                    refs.append({
                        "type": "paper",
                        "title": title,
                        "authors": authors,
                        "source": source,
                        "url": f"https://doi.org/{doi}" if doi.startswith("10.") else doi,
                        "doi": doi,
                        "date": date
                    })
                    seen_titles.add(title)

        # 提取行业新闻部分
        # 格式: **新闻标题** (bold) + **来源**: ... **原文链接**: ...
        news_pattern = r'\*\*([^*]+)\*\*[^\n]*\n\s*\*\*来源\*\*:\s*([^\n]+)\s*\n\s*\*\*原文链接\*\*:\s*([^\n]+)'

        for match in re.finditer(news_pattern, markdown_text, re.MULTILINE):
            title = match.group(1).strip()
            source = match.group(2).strip()
            url = match.group(3).strip()

            if title and title not in seen_titles:
                refs.append({
                    "type": "news",
                    "title": title,
                    "authors": "",
                    "source": source,
                    "url": url,
                    "date": date
                })
                seen_titles.add(title)

        return refs

    def format_bibliography(self, references: list[dict] = None, style: str = "cssci") -> str:
        """
        格式化为 CSSCI 参考文献格式

        Args:
            references: 参考文献列表，如果为 None 则使用 self.references
            style: 格式风格，目前支持 "cssci"

        Returns:
            str: 格式化后的参考文献列表
        """
        refs = references or self.references
        if not refs:
            return ""

        lines = ["\n\n---\n\n## 参考文献\n"]

        for i, ref in enumerate(refs, 1):
            formatted = self._format_single_reference(ref)
            lines.append(f"[{i}] {formatted}")

        return "\n".join(lines)

    def _format_single_reference(self, ref: dict) -> str:
        """格式化单条参考文献"""
        ref_type = ref.get("type", "paper")
        title = ref.get("title", "")
        authors = ref.get("authors", "")
        source = ref.get("source", "")
        url = ref.get("url", "")
        date = ref.get("date", "")

        if ref_type == "paper":
            # 期刊论文格式：作者. 题名[J]. 期刊, 年.
            year = date[:4] if date else ""
            venue = source.replace(f", {year}", "") if year else source

            if authors:
                formatted = f"{authors}. {title}[J]. {venue}, {year}."
            else:
                formatted = f"{title}[J]. {venue}, {year}."

        elif ref_type == "news":
            # 新闻格式：作者. 标题[N]. 来源, 日期.
            if authors:
                formatted = f"{authors}. {title}[N]. {source}, {date}."
            else:
                formatted = f"{title}[N]. {source}, {date}."

        else:
            formatted = f"{title}. {source}, {date}."

        # 添加 URL
        if url and url.startswith("http"):
            formatted += f" URL: {url}"

        return formatted

    def get_citation_map(self) -> dict:
        """
        获取标题到引用编号的映射，用于正文中插入引用标记

        Returns:
            dict: {title: "[1]"} 格式的映射
        """
        citation_map = {}
        for i, ref in enumerate(self.references, 1):
            citation_map[ref["title"]] = f"[{i}]"
        return citation_map
