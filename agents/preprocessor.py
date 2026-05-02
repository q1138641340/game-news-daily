"""
预处理 Agent
将 HTML 转为纯文本 Markdown，过滤无关内容，提取结构化信息
"""

from tools.llm import get_collect_deepseek, get_collect_minimax
from tools.json_parser import parse_json
import logging
import requests

logger = logging.getLogger(__name__)


class PreprocessorAgent:
    """预处理 Agent：HTML -> 结构化 Markdown"""

    SYSTEM_PROMPT = """你是一位学术内容预处理器，专门处理游戏研究与跨媒体艺术领域的论文和文章。

给定原始内容（HTML 或混乱文本），你的任务是：

1. 提取核心文章/论文内容
2. 移除导航栏、广告、页脚、弹窗
3. 保留重要结构：标题、列表、引用

## 对于学术论文，必须提取以下结构化信息：

### 标题
[论文英文标题]

### 研究背景
[1-2句说明研究动机和问题]

### 研究方法
[1-2句概述方法论]

### 核心发现
[2-3句描述主要结论]

### 【重点】对游戏研究/跨媒体艺术的启示
[这是最重要的部分，必须详细说明：
- 该研究对游戏研究/媒介理论/叙事学/交互设计有什么具体启示
- 可以如何应用于游戏开发、游戏分析、或游戏批评
- 理论与实践的结合点在哪里
- 如果看似无关，说明为何仍然值得关注或直接标记为"低相关"]

### 关联领域标签
[用逗号分隔的相关领域，如：game-studies, narratology, media-theory, hci, ai-games]

## 对于新闻报道：

### 标题
### 事件背景
### 核心要点
### 对游戏/数字媒体行业的影响
### 关联领域标签

## 规则：
- 只输出处理后的 Markdown
- 保留所有技术术语和专有名词
- **启示部分是必填项，不能留空或省略**
- 对于明显与游戏/跨媒体艺术无关的论文，在启示部分标注"【低相关警告】：本文属于 [领域]，与游戏研究关联度低"
- 不要解释你的操作过程"""

    def __init__(self, config: dict):
        self.config = config
        self.llm, self.model = get_collect_deepseek()  # DeepSeek Pro 用于结构提取
        self.mm_client, self.mm_model = get_collect_minimax()  # MiniMax 用于LLM精炼（更稳定）

    def run(self, items: list[dict]) -> list[dict]:
        """
        批量预处理收集到的内容

        Args:
            items: 收集到的条目列表，每条包含 url, summary 等字段

        Returns:
            添加了 clean_content 字段的条目列表
        """
        logger.info(f"  预处理 {len(items)} 条内容...")

        for i, item in enumerate(items):
            try:
                content = item.get("full_content", "") or item.get("summary", "")

                if not content or len(content) < 50:
                    # 内容太少，尝试爬取
                    if item.get("url"):
                        from tools.web_scraper import WebScraper
                        scraper = WebScraper(timeout=20)
                        page = scraper.fetch(item["url"])
                        if page:
                            content = page.get("html", "")

                        # arXiv 专用：URL 样式 /abs/xxxx 或 arxiv.org/abs/xxxx 尝试 API
                        if not content and "arxiv.org" in (item.get("url") or ""):
                            arxiv_id = self._extract_arxiv_id(item["url"])
                            if arxiv_id:
                                content = self._fetch_arxiv_api(arxiv_id)

                if not content:
                    continue

                # 步骤1: 本地 HTML -> Markdown（快速，免费）
                from tools.web_scraper import WebScraper
                if "<" in content and ">" in content:
                    markdown = WebScraper.html_to_markdown(content)
                else:
                    markdown = content

                # 步骤2: 如果内容超过1500字符，用LLM进一步精炼
                if len(markdown) > 1500:
                    markdown = self._llm_refine(markdown, item)

                # 步骤3: 截断过长内容（节省后续token）
                if len(markdown) > 3000:
                    markdown = markdown[:3000] + "\n\n[Content truncated]"

                item["clean_content"] = markdown

            except Exception as e:
                logger.warning(f"    [预处理失败] {item.get('title', '')[:30]}: {e}")
                # 保留原始摘要作为备用
                item["clean_content"] = item.get("summary", "")

        # 过滤掉没有有效内容的条目
        valid = [item for item in items if item.get("clean_content")]

        logger.info(f"  预处理完成，有效内容 {len(valid)}/{len(items)} 条")
        return valid

    def _llm_refine(self, text: str, item: dict) -> str:
        """使用 LLM 精炼内容（MiniMax 优先，DeepSeek 备用）"""
        title = item.get("title", "")
        venue = item.get("venue", "")
        source = item.get("source", "")

        context = f"""论文标题: {title}
期刊/来源: {venue or source}
原文内容:
{text[:3000]}"""

        try:
            result = self.mm_client.chat(
                system_prompt=self.SYSTEM_PROMPT,
                user_message=f"请提取并精炼以下学术论文的要点，特别关注「对游戏研究的启示」：\n\n{context}",
                model=self.mm_model,
                temperature=0.1,
                max_tokens=1500
            )
            return result
        except Exception:
            logger.warning("    [MiniMax精炼失败，尝试DeepSeek]")
            pass

        # 备用 DeepSeek
        try:
            result = self.llm.chat(
                system_prompt=self.SYSTEM_PROMPT,
                user_message=f"请提取并精炼以下学术论文的要点，特别关注「对游戏研究的启示」：\n\n{context}",
                model=self.model,
                temperature=0.1,
                max_tokens=1500
            )
            return result
        except Exception:
            logger.warning("    [DeepSeek也失败，保留本地处理结果]")
            # LLM 失败时，保留本地处理结果
            return text

    def _extract_arxiv_id(self, url: str) -> str:
        """从 URL 中提取 arXiv ID"""
        import re
        patterns = [
            r'arxiv\.org/abs/(\d+\.\d+)',
            r'arxiv\.org/pdf/(\d+\.\d+)',
        ]
        for p in patterns:
            m = re.search(p, url)
            if m:
                return m.group(1)
        return ""

    def _fetch_arxiv_api(self, arxiv_id: str) -> str:
        """通过 arXiv API 获取摘要（绕过爬虫）"""
        try:
            url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                # 简单提取摘要文本
                text = resp.text
                start = text.find("<summary>") + 9
                end = text.find("</summary>")
                if start > 8 and end > start:
                    return text[start:end].strip()
        except Exception:
            logger.warning(f"    [arXiv API获取失败] {arxiv_id}")
            pass
        return ""
