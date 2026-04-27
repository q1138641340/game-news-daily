"""
收集 Agent 2: 学术论文收集
负责 arXiv、Semantic Scholar、CrossRef 等学术源
"""

import requests
from datetime import datetime, timedelta, timezone
from typing import Optional
from tools.llm import get_collect_deepseek_flash, get_collect_minimax
from tools.json_parser import parse_json
import logging

logger = logging.getLogger(__name__)


class AcademicCollectorAgent:
    """学术论文收集 Agent"""

    SYSTEM_PROMPT = """你是一位学术论文整理助手，专门处理游戏研究及相关领域的论文（游戏学、叙事学、媒介理论、技术哲学、计算机科学、人机交互）。

给定原始论文条目，你的任务是：
1. 去除重复论文
2. 标准化格式：标题、作者（完整列表）、摘要（精简版关键发现2-4句）、URL、DOI、期刊/会议、发表日期
3. 评估与游戏研究的相关性（0-1，0=不相关，1=高度相关）
4. 保留相关性 >= 0.3 的论文
5. 分类：game-studies（游戏研究）、narratology（叙事学）、media-theory（媒介理论）、ai-games（游戏AI）、hci（人机交互）、cs-graphics（计算机图形）、cs-ai（人工智能）、methodology（方法论）、chinese-academic（国内学术）

关于作者格式：
- 英文名：姓，名（格式：LastName, FirstName 或 LastName F.）
- 中文名：姓+名（格式：张三）
- 多个作者用逗号分隔，最多列出前8位

关于DOI：
- arXiv论文格式：10.48550/arXiv.XXXXXXX
- 期刊论文格式：10.XXXX/xxxxx

返回JSON数组。每条必须包含：
- title: string
- authors: string（逗号分隔的完整作者列表）
- abstract: string（关键发现2-4句）
- url: string
- doi: string 或 null
- pdf_url: string 或 null
- venue: string（期刊/会议名称，英文缩写可保留）
- published_date: string（YYYY-MM-DD格式）
- relevance: float（0-1）
- category: string

重要：只返回JSON数组，不要解释，不要代码块包裹。"""

    def __init__(self, config: dict):
        self.config = config
        self.mm_client, self.mm_model = get_collect_minimax()
        self.ds_client, self.ds_model = get_collect_deepseek_flash()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'GameResearchBot/1.0 (academic research)'
        })

    def run(self) -> list[dict]:
        """执行完整的论文收集流程"""
        all_papers = []

        # 从配置读取关键词
        academic_kw = self.config.get("academic_keywords", {})
        tech_kw = academic_kw.get("tech", [])
        humanities_kw = academic_kw.get("humanities", [])
        zh_kw = academic_kw.get("zh", [])

        # 步骤1: arXiv（技术类论文）
        logger.info("  [1/4] arXiv 论文（技术类）...")
        arxiv_papers = self._collect_arxiv(tech_kw)
        all_papers.extend(arxiv_papers)
        logger.info(f"        arXiv 获取 {len(arxiv_papers)} 篇")

        # 步骤2: Semantic Scholar（人文艺术类）
        logger.info("  [2/4] Semantic Scholar（人文艺术类）...")
        ss_papers = self._collect_semantic_scholar(humanities_kw)
        all_papers.extend(ss_papers)
        logger.info(f"        Semantic Scholar 获取 {len(ss_papers)} 篇")

        # 步骤3: CrossRef（人文艺术 + 中文期刊）
        logger.info("  [3/4] CrossRef 期刊（人文+中文）...")
        crossref_papers = self._collect_crossref(humanities_kw + zh_kw)
        all_papers.extend(crossref_papers)
        logger.info(f"        CrossRef 获取 {len(crossref_papers)} 篇")

        # 步骤4: DBLP（计算机科学文献）
        logger.info("  [4/4] DBLP 计算机科学...")
        dblp_papers = self._collect_dblp()
        all_papers.extend(dblp_papers)
        logger.info(f"        DBLP 获取 {len(dblp_papers)} 篇")

        # LLM 清洗和评估
        if all_papers:
            cleaned = self._clean_with_llm(all_papers)
            logger.info(f"        清洗后 {len(cleaned)} 篇")
            return cleaned

        return []

    def _collect_arxiv(self, queries: list[str]) -> list[dict]:
        """从 arXiv 收集论文（带速率限制保护）"""
        import time

        all_papers = []
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)

        for i, query in enumerate(queries):
            if i > 0:
                time.sleep(30)  # arXiv限制：每小时最多3次请求，约30秒间隔

            for attempt in range(4):  # 增加重试次数
                try:
                    url = "http://export.arxiv.org/api/query"
                    params = {
                        "search_query": f"all:{query}",
                        "start": 0,
                        "max_results": 5,
                        "sortBy": "submittedDate",
                        "sortOrder": "descending"
                    }
                    resp = self.session.get(url, params=params, timeout=30)

                    # 429 Too Many Requests
                    if resp.status_code == 429:
                        if attempt < 3:
                            wait_time = 60 * (attempt + 1)  # 指数退避
                            logger.warning(f"        [arXiv限速，等待{wait_time}秒重试...]")
                            time.sleep(wait_time)
                            continue
                        else:
                            logger.warning(f"        [arXiv失败] {query}: 速率限制")
                            break

                    # 502 Bad Gateway 等服务器错误
                    if resp.status_code >= 500:
                        if attempt < 3:
                            wait_time = 30 * (attempt + 1)
                            logger.warning(f"        [arXiv服务器错误，等待{wait_time}秒重试...]")
                            time.sleep(wait_time)
                            continue
                        else:
                            logger.warning(f"        [arXiv失败] {query}: 服务器错误 {resp.status_code}")
                            break

                    resp.raise_for_status()
                    papers = self._parse_arxiv_xml(resp.text, cutoff)
                    if papers:
                        logger.info(f"        [arXiv成功] {query}: {len(papers)} 篇")
                    else:
                        logger.info(f"        [arXiv无结果] {query}")
                    all_papers.extend(papers)
                    break

                except Exception as e:
                    if attempt < 3:
                        wait_time = 10 * (attempt + 1)
                        time.sleep(wait_time)
                    else:
                        logger.warning(f"        [arXiv失败] {query}: {str(e)[:60]}")

        # 去重
        seen = set()
        unique = []
        for p in all_papers:
            if p["url"] not in seen:
                seen.add(p["url"])
                unique.append(p)

        return unique

    def _collect_semantic_scholar(self, queries: list[str] = None) -> list[dict]:
        """从 Semantic Scholar 收集论文（带速率限制保护）"""
        import time

        if queries is None:
            queries = [
                "game studies narratology",
                "video game media theory",
                "game design procedural",
                "ludology",
                "game user research",
            ]
        else:
            # 最多取5个最相关的人文类关键词，避免rate limit
            queries = queries[:5]

        all_papers = []

        for i, query in enumerate(queries):
            if i > 0:
                time.sleep(8)  # 增加间隔降低限速

            for attempt in range(3):
                try:
                    url = "https://api.semanticscholar.org/graph/v1/paper/search"
                    params = {
                        "query": query,
                        "limit": 5,
                        "fields": "title,authors,abstract,url,externalIds,venue,publicationDate,openAccessPdf",
                        "year": f"{datetime.now().year-1}-{datetime.now().year}"
                    }
                    resp = self.session.get(url, params=params, timeout=20)

                    if resp.status_code == 429:
                        if attempt < 2:
                            wait_time = 20 * (attempt + 1)  # 指数退避
                            logger.warning(f"        [SS限速，等待{wait_time}秒重试...]")
                            time.sleep(wait_time)
                            continue
                        else:
                            logger.warning(f"        [SS失败] {query}: 速率限制")
                            break

                    resp.raise_for_status()
                    data = resp.json()

                    for paper in data.get("data", []):
                        doi = paper.get("externalIds", {}).get("DOI")
                        pdf_info = paper.get("openAccessPdf")

                        all_papers.append({
                            "title": paper.get("title", ""),
                            "authors": ", ".join(
                                a.get("name", "") for a in (paper.get("authors") or [])[:5]
                            ),
                            "abstract": (paper.get("abstract") or "")[:500],
                            "url": paper.get("url", ""),
                            "doi": doi or "",
                            "pdf_url": pdf_info.get("url") if pdf_info else "",
                            "venue": paper.get("venue", ""),
                            "published_date": paper.get("publicationDate", ""),
                            "category": "pending"
                        })

                    if len(data.get("data", [])) > 0:
                        logger.info(f"        [SS成功] {query}: {len(data['data'])} 篇")
                    break

                except Exception as e:
                    if attempt < 2:
                        wait_time = 5 * (attempt + 1)
                        time.sleep(wait_time)
                    else:
                        logger.warning(f"        [SS失败] {query}: {str(e)[:60]}")

        # 去重
        seen = set()
        unique = []
        for p in all_papers:
            key = p.get("doi") or p["url"]
            if key not in seen:
                seen.add(key)
                unique.append(p)

        return unique

    def _collect_crossref(self, queries: list[str] = None) -> list[dict]:
        """从 CrossRef 收集期刊论文（国际+国内）"""
        if queries is None:
            queries = [
                "game narrative",
                "game studies",
                "interactive storytelling",
                "video game",
                "ludology",
                "游戏叙事",
                "游戏研究",
                "人机交互 游戏",
            ]

        all_papers = []
        seen_dois = set()

        for query in queries:
            try:
                url = "https://api.crossref.org/works"
                params = {
                    "query": query,
                    "rows": 5,
                    "sort": "published",
                    "order": "desc",
                    "filter": f"from-pub-date:{(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')}"
                }
                # CrossRef 要求 mailto 参数以获得更好的速率
                headers = {"User-Agent": "GameResearchBot/1.0 (mailto:research@example.com)"}
                resp = self.session.get(url, params=params, headers=headers, timeout=15)
                resp.raise_for_status()
                data = resp.json()

                for item in data.get("message", {}).get("items", []):
                    title_list = item.get("title", [])
                    title = title_list[0] if title_list else ""

                    authors = ", ".join(
                        f"{a.get('given', '')} {a.get('family', '')}".strip()
                        for a in (item.get("author") or [])[:5]
                    )

                    doi = item.get("DOI", "")
                    date_parts = item.get("published-print", item.get("published-online", {}))
                    date_parts = date_parts.get("date-parts", [[None]])
                    pub_date = ""
                    if date_parts and date_parts[0]:
                        parts = date_parts[0]
                        if len(parts) >= 3 and all(parts):
                            pub_date = f"{parts[0]}-{parts[1]:02d}-{parts[2]:02d}"
                        elif len(parts) >= 2 and all(parts):
                            pub_date = f"{parts[0]}-{parts[1]:02d}"

                    all_papers.append({
                        "title": title,
                        "authors": authors,
                        "abstract": item.get("abstract", "").replace("<jats:p>", "").replace("</jats:p>", "").replace("<jats:italic>", "").replace("</jats:italic>", "")[:500],
                        "url": f"https://doi.org/{doi}" if doi else "",
                        "doi": doi,
                        "pdf_url": "",
                        "venue": item.get("container-title", [""])[0],
                        "published_date": pub_date,
                        "category": "pending"
                    })

            except Exception as e:
                logger.warning(f"        [CrossRef失败] {query}: {e}")

        # 去重
        seen = set()
        unique = []
        for p in all_papers:
            key = p.get("doi") or p["title"]
            if key not in seen:
                seen.add(key)
                unique.append(p)

        return unique

    def _clean_with_llm(self, papers: list[dict]) -> list[dict]:
        """使用LLM清洗和评估论文（MiniMax）"""
        if not papers:
            return papers
        try:
            input_data = str(papers[:50])
            result = self.mm_client.chat_json(
                system_prompt=self.SYSTEM_PROMPT,
                user_message=f"请清洗、评估并分类以下学术论文，返回JSON数组：\n{input_data}",
                model=self.mm_model,
                temperature=0.1
            )
            if isinstance(result, list):
                return [p for p in result if p.get("relevance", 0) >= 0.3]
        except Exception as e:
            logger.warning(f"        [MiniMax清洗失败，尝试DeepSeek Flash]: {e}")
            try:
                result = self.ds_client.chat_json(
                    system_prompt=self.SYSTEM_PROMPT,
                    user_message=f"请清洗、评估并分类以下学术论文，返回JSON数组：\n{input_data}",
                    model=self.ds_model,
                    temperature=0.1
                )
                if isinstance(result, list):
                    return [p for p in result if p.get("relevance", 0) >= 0.3]
            except Exception as e2:
                logger.warning(f"        [DeepSeek Flash 也失败，使用原始数据]: {e2}")

        return papers

    def _collect_dblp(self) -> list[dict]:
        """从 DBLP 收集计算机科学论文（含国内学者英文论文）"""
        import time

        queries = [
            "game narrative",
            "procedural content generation",
            "game AI",
            "virtual reality game",
        ]

        all_papers = []

        for query in queries:
            for attempt in range(3):
                try:
                    time.sleep(5 * (attempt + 1))  # 指数退避
                    url = "https://dblp.org/search/publ/api"
                    params = {
                        "q": query,
                        "h": 5,
                        "format": "json",
                        "sortBy": "date",
                        "sortOrder": "desc"
                    }
                    resp = self.session.get(url, params=params, timeout=20)
                    resp.raise_for_status()
                    data = resp.json()

                    hits = data.get("result", {}).get("hits", {}).get("hit", [])
                    if isinstance(hits, dict):
                        hits = [hits]

                    for hit in hits:
                        info = hit.get("info", {})
                        authors_list = info.get("authors", {}).get("author", [])
                        if isinstance(authors_list, dict):
                            authors_list = [authors_list]
                        authors = ", ".join(a.get("text", "") for a in authors_list[:5])

                        title = info.get("title", "")
                        venue = info.get("venue", "")
                        year = info.get("year", "")
                        url_str = info.get("url", "")
                        doi = info.get("doi", "")

                        all_papers.append({
                            "title": title,
                            "authors": authors,
                            "abstract": "",
                            "url": url_str or (f"https://doi.org/{doi}" if doi else ""),
                            "doi": doi,
                            "pdf_url": "",
                            "venue": venue,
                            "published_date": f"{year}-01-01" if year else "",
                            "category": "pending"
                        })

                    if hits:
                        logger.info(f"        [DBLP成功] {query}: {len(hits)} 篇")
                    break

                except Exception as e:
                    if attempt < 2:
                        continue
                    else:
                        logger.warning(f"        [DBLP失败] {query}: {str(e)[:60]}")

        # 去重
        seen = set()
        unique = []
        for p in all_papers:
            key = p.get("doi") or p["title"]
            if key and key not in seen:
                seen.add(key)
                unique.append(p)

        return unique

    @staticmethod
    def _parse_arxiv_xml(xml_text: str, cutoff: datetime) -> list[dict]:
        """解析 arXiv API 返回的 XML"""
        import xml.etree.ElementTree as ET

        papers = []
        ns = {
            'atom': 'http://www.w3.org/2005/Atom',
            'arxiv': 'http://arxiv.org/schemas/atom'
        }

        try:
            root = ET.fromstring(xml_text)
            for entry in root.findall('atom:entry', ns):
                title = entry.find('atom:title', ns)
                title_text = title.text.strip().replace('\n', ' ') if title is not None else ""

                summary = entry.find('atom:summary', ns)
                summary_text = summary.text.strip()[:500] if summary is not None else ""

                link = entry.find('atom:id', ns)
                url = link.text.strip() if link is not None else ""

                # arXiv ID
                arxiv_id = url.split('/')[-1] if url else ""

                authors = ", ".join(
                    a.find('atom:name', ns).text
                    for a in entry.findall('atom:author', ns)
                    if a.find('atom:name', ns) is not None
                )[:200]

                published = entry.find('atom:published', ns)
                pub_date = ""
                if published is not None:
                    try:
                        dt = datetime.fromisoformat(published.text.strip().replace('Z', '+00:00'))
                        if dt < cutoff:
                            continue
                        pub_date = dt.strftime("%Y-%m-%d")
                    except Exception:
                        pass

                # PDF 链接
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

                # 分类
                categories = [c.get('term', '') for c in entry.findall('atom:category', ns)]
                primary = entry.find('arxiv:primary_category', ns)
                if primary is not None:
                    categories.insert(0, primary.get('term', ''))

                papers.append({
                    "title": title_text,
                    "authors": authors,
                    "abstract": summary_text,
                    "url": url,
                    "doi": f"10.48550/arXiv.{arxiv_id}",
                    "pdf_url": pdf_url,
                    "venue": "arXiv",
                    "published_date": pub_date,
                    "category": "pending"
                })

        except Exception as e:
            logger.warning(f"        [arXiv XML解析失败]: {e}")

        return papers