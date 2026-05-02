"""
整理输出 Agent
将审查通过的内容整理为正式的 Obsidian Markdown 日报
"""

from datetime import datetime
from typing import Optional
from tools.llm import get_format_deepseek
import logging

logger = logging.getLogger(__name__)


class FormatterAgent:
    """整理输出 Agent"""

    SYSTEM_PROMPT = """你是一位资深学术编辑，负责将学术论文和行业新闻整理为高水平的 Markdown 研究日报。

所有输出必须使用中文，措辞严谨、流畅、具有高水平学术阅读性。

## 报告结构

### 1. 日期标题
使用正式标题格式：## 研究日报 YYYY-MM-DD

### 2. 执行摘要（200字左右）
- 概述当日最重要的3-5项内容
- 涵盖学术前沿、行业动态、研究趋势
- 使用学术化语言，客观陈述

### 3. 学术论文（核心部分）

按研究领域分组，每组包含：

#### 论文标题（英文原文）
**作者**: [完整作者列表，格式：姓，名 或 中文姓名]
**来源**: [期刊/会议全称，发表年份]
**DOI/PDF**: [链接]
**摘要**:
[详细摘要，200-400字，包含：
- 研究背景与动机
- 研究方法与技术路线
- 核心发现与创新点
- 研究意义与局限]
**关联领域**: [游戏研究相关标签]

#### 格式要求
- 每篇论文必须有完整作者信息
- DOI 链接必须提供
- PDF 可下载的要标注
- 英文论文标题保留原文，作者名保留原文但加中文说明

### 4. 行业新闻（深度报道风格）

每条新闻包含：
- 标题（中文）
- **来源**: [媒体/机构名称，发表日期]
- **原文链接**: [URL]
- **内容概述**: [300-500字，深度分析]
  - 事件背景
  - 核心要点
  - 影响与意义
  - 与研究领域的关联

### 5. 趋势与关联分析（文献综述风格）

本部分是核心，要求：

#### 论文与新闻的关联分析
[从多个角度分析：
- 理论与实践的互动
- 技术发展对研究范式的影响
- 跨领域知识的迁移

每个关联点需说明来源]

#### 值得关注的新趋势
[从以下维度分析：
1. **技术前沿**: [具体技术趋势及来源]
2. **理论发展**: [理论进展及学术来源]
3. **产业应用**: [应用趋势及行业来源]
4. **方法论创新**: [研究方法创新及来源]
5. **跨学科动向**: [跨领域趋势及来源]

每个趋势必须有明确的学术或行业来源支撑]

### 6. 推荐阅读

Top 3 必读条目：
- 条目名称
- **类型**: [论文/新闻]
- **推荐理由**: [200字左右，说明为何必读]
- **来源**: [完整来源信息]

### 7. 参考来源总览

列出本次日报引用的所有来源：
- 学术期刊/会议
- 新闻媒体
- 行业报告

## 格式规范

- 使用 Markdown 标题层级（##, ###, ####）
- 所有链接使用行内链接格式 [标题](URL)
- 论文引用格式：[序号] 作者. 标题. 期刊, 年份. URL
- 主要章节之间使用 --- 分隔
- 不使用 emoji
- 严谨的学术写作风格
- 每个数据、观点必须标注来源

只输出 Markdown 内容，不要任何解释。"""

    def __init__(self, config: dict):
        self.config = config
        self.llm, self.model = get_format_deepseek()  # DeepSeek V4 整理

    def run(self, items: list[dict]) -> str:
        """
        整理并生成日报

        Args:
            items: 通过双重审查的条目列表

        Returns:
            完整的 Markdown 日报内容（不含 frontmatter）
        """
        if not items:
            return self._empty_report()

        # 最终去重检查（标题相似度）
        items = self._final_dedup(items)

        # 按类型分组
        papers = [item for item in items if item.get("category", "") in
                  ("game-studies", "narratology", "media-theory", "ai-games",
                   "hci", "cs-graphics", "cs-ai", "methodology", "academic")]
        news = [item for item in items if item not in papers]

        # 准备输入数据
        input_data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "papers": [
                {
                    "title": p.get("title", ""),
                    "authors": p.get("authors", ""),
                    "abstract": p.get("clean_content", "") or p.get("summary", "") or p.get("abstract", ""),
                    "venue": p.get("venue", ""),
                    "doi": p.get("doi", ""),
                    "url": p.get("url", ""),
                    "pdf_available": bool(p.get("pdf_url")),
                    "priority": p.get("priority", "medium"),
                    "interest_areas": p.get("interest_areas", [])
                }
                for p in papers
            ],
            "news": [
                {
                    "title": n.get("title", ""),
                    "summary": n.get("clean_content", "") or n.get("summary", ""),
                    "source": n.get("source", ""),
                    "url": n.get("url", ""),
                    "category": n.get("category", ""),
                    "priority": n.get("priority", "medium"),
                    "needs_verification": n.get("needs_verification", False),
                    "verification_sources": n.get("verification_sources", [])
                }
                for n in news
            ]
        }

        # 调用 LLM 生成报告
        logger.info(f"  生成日报: {len(papers)} 篇论文 + {len(news)} 条新闻...")

        try:
            report = self.llm.chat(
                system_prompt=self.SYSTEM_PROMPT,
                user_message=f"请根据以下内容生成今日研究日报（全部使用中文）：\n{input_data}",
                model=self.model,
                temperature=0.4,
                max_tokens=16000
            )
            # 后处理：追加战略增强内容（不改动原有结构）
            report = self._add_strategic_enhancements(report, papers, news)
            return report
        except Exception as e:
            logger.warning(f"  [LLM生成失败]: {e}")
            return self._fallback_report(papers, news)

    def _add_strategic_enhancements(self, report: str, papers: list[dict], news: list[dict]) -> str:
        """
        在日报末尾追加三项战略增强内容，不改动原有结构。
        """
        if not report or len(report.strip()) < 100:
            return report

        ENHANCEMENT_SYSTEM = """你是一位战略分析专家，负责为学术日报追加批判性增强内容。
严格遵循用户的三项要求，输出必须全部使用中文。"""

        all_titles = [p.get("title", "") for p in papers] + [n.get("title", "") for n in news]
        all_abstracts = (
            [p.get("clean_content", "") or p.get("summary", "") for p in papers] +
            [n.get("clean_content", "") or n.get("summary", "") for n in news]
        )
        paper_count = len(papers)
        news_count = len(news)

        user_msg = f"""以下是一份学术日报的原文，请在末尾追加三项战略增强内容，**绝对不要改动原文**。

---日报原文开始---
{report}
---日报原文结束---

今日数据：{paper_count} 篇论文，{news_count} 条新闻。

请严格按以下三项要求输出：

**要求一（核心张力声明）**
在执行摘要的末尾追加一行，格式为：
"本日报追踪到的最核心的结构性张力在于：……"
要求：必须是对今日内容中浮现的深层矛盾或两条相反逻辑的凝练，必须具有可跨期追踪的理论潜力，避免泛泛而谈。直接给出这句话即可，不需要前缀说明。

**要求二（反向思考）**
在"趋势与关联分析"部分的"值得关注的新趋势"中，为每一条趋势追加一个"然而"段，格式为：
"然而，这一趋势的潜在局限/风险/反例在于：……"
要求：必须是对该趋势可能失败、被夸大或存在盲区的批判性思考，需有实质内容，不可仅为措辞性否定。每条趋势都要追加。

**要求三（本周研究路径）**
将"推荐阅读"升级为"本周研究路径"，格式如下：
**本周研究路径：【路径标题】**
1. 先读《…》（说明阅读目的）。
2. 再读《…》（说明如何在第一条基础上深化）。
3. 最后读《…》（说明如何整合前三者）。
**核心研讨问题**：提出1个能够串联所有推荐内容的深度问题。

输出格式：
在日报原文之后，插入分隔线"**以下为战略增强内容**"，然后依次输出上述三项内容。不要重复日报原文，只输出增强内容。"""

        try:
            enhancements = self.llm.chat(
                system_prompt=ENHANCEMENT_SYSTEM,
                user_message=user_msg,
                model=self.model,
                temperature=0.5,
                max_tokens=8000
            )
            if enhancements and len(enhancements.strip()) > 50:
                return f"{report.strip()}\n\n---\n\n**以下为战略增强内容**\n\n{enhancements.strip()}"
        except Exception as e:
            logger.warning(f"  [战略增强生成失败]: {e}")

        return report

    def _empty_report(self) -> str:
        """空日报"""
        date = datetime.now().strftime("%Y-%m-%d")
        return f"""## 今日无符合条件的内容

日期：{date}

今日没有通过审查的内容。

可能原因：
- 没有符合您研究兴趣的新发表或新闻
- 所有收集的内容在质量审查阶段被过滤
- API 速率限制或网络问题导致数据收集失败

请检查配置后重试。"""

    def _final_dedup(self, items: list[dict]) -> list[dict]:
        """最终去重：按标题Jaccard相似度去除重复论文/新闻"""
        if len(items) <= 3:
            return items

        import re

        seen_sigs = set()
        result = []

        for item in items:
            title = (item.get("title", "") or "").strip().lower()
            # 归一化：去除标点，压缩空格
            sig = re.sub(r'[^\w\s]', '', title)
            sig = re.sub(r'\s+', ' ', sig).strip()

            if len(sig) < 10:  # 标题太短不参与去重
                result.append(item)
                continue

            # 检查是否与已有标题过于相似
            is_dup = False
            for seen_sig in seen_sigs:
                if self._title_similarity(sig, seen_sig) > 0.85:
                    is_dup = True
                    break

            if not is_dup:
                seen_sigs.add(sig)
                result.append(item)

        if len(items) > len(result):
            logger.info(f"  [最终去重] 过滤 {len(items) - len(result)} 条重复标题")

        return result

    @staticmethod
    def _title_similarity(t1: str, t2: str) -> float:
        """计算两个标题的 Jaccard 相似度（基于词集）"""
        words1 = set(t1.split())
        words2 = set(t2.split())
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union) if union else 0.0

    def _fallback_report(self, papers: list[dict], news: list[dict]) -> str:
        """降级方案：不使用LLM，直接格式化（中文）"""
        date = datetime.now().strftime("%Y-%m-%d")
        lines = [f"## 研究日报 - {date}", ""]

        if papers:
            lines.append("### 学术论文")
            lines.append("")
            for p in papers:
                title = p.get("title", "无标题")
                authors = p.get("authors", "未知作者")
                venue = p.get("venue", "")
                url = p.get("url", "")
                doi = p.get("doi", "")
                pdf = " [PDF]" if p.get("pdf_url") else ""

                lines.append(f"**{title}**")
                lines.append(f"- 作者：{authors}")
                if venue:
                    lines.append(f"- 来源：{venue}")
                if url:
                    lines.append(f"- 链接：{url}")
                if doi:
                    lines.append(f"- DOI：[{doi}](https://doi.org/{doi})")
                lines.append("")

        if news:
            lines.append("---")
            lines.append("")
            lines.append("### 行业新闻")
            lines.append("")
            for n in news:
                title = n.get("title", "无标题")
                source = n.get("source", "")
                url = n.get("url", "")
                summary = n.get("summary", "")

                lines.append(f"**{title}**")
                if source:
                    lines.append(f"- 来源：{source}")
                if url:
                    lines.append(f"- 链接：{url}")
                if summary:
                    lines.append(f"- {summary[:200]}")
                lines.append("")

        return "\n".join(lines)
