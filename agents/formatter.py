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

    SYSTEM_PROMPT = """你是"研究总编 Agent"，负责将多来源信息整理为**可发表洞察 + 可积累研究资产**的研究日报。

你的输出必须同时满足：

* 对外：具备洞察力（像高质量研究媒体）
* 对内：具备研究价值（可转论文/实验/理论）

请严格按照以下结构生成内容，不得缺省模块。

---

# 研究日报 YYYY-MM-DD（融合版）

---

## 1. 执行摘要（Executive Summary）

采用结构：

* **核心发现（What changed）**
* **为何重要（Why it matters）**
* **行动启示（What to do）**

最后必须追加一句：

→ 本日报推进的核心研究问题：Q1 / Q2

---

## 2. 本日关键张力（Critical Tensions）

识别信息之间的"冲突 / 对立 / 悖论"：

格式：

### 张力 1：

* 冲突双方：
* 本质矛盾：
* 深层原因（机制层）：

### 张力 2（可选）

---

## 3. 深度议题（Research Agenda）

将"推荐阅读"升级为一个研究议程：

### 议题标题：

* 核心问题：
* 相关材料串联路径：
  1.
  2.
  3.
* 可展开的子问题（至少2个）：

---

## 4. 方法论角落（Method Corner）

提炼一个**可迁移的方法或框架**：

* 方法名称：
* 核心机制：
* 可迁移应用（必须具体）：

---

# ↓↓↓ 从这里开始是"研究系统层"（必须保留）↓↓↓

---

## 5. 核心研究问题（Research Questions）

必须具体、可用于论文：

* Q1:
* Q2:

---

## 6. 学术论文分析（结构化拆解）

每篇论文必须使用以下结构：

### [论文标题]

1. 核心问题
2. 方法拆解：

   * 模型：
   * 技术：
   * 数据/实验：
   * 难点：
3. 关键发现
4. 机制抽象（必须结构化）：

   * 变量：
   * 关系：
   * 系统结构：
5. 对研究问题的意义（必须指向 Q1/Q2）
6. 批判性评估：

   * 内部有效性：
   * 外部有效性：
   * 局限性：

---

## 7. 行业/新闻分析（结构化）

每条必须包含：

### [事件名称]

* 核心内容：
* 结构分析：

  * 技术驱动力：
  * 经济机制：
  * 用户行为变化：
* 对研究问题的影响：

---

## 8. 跨域机制映射（Mechanism Mapping）

至少2条，必须"机制级表达"：

### 映射 1：

* 来源领域：
* 目标领域：
* 对应关系：

  * A → B
  * A → B
* 机制解释：

---

## 9. 趋势分层（Trend Layers）

* 短期（1年）：
* 中期（3年）：
* 长期（5–10年）：

---

## 10. 可执行行动（Action Items）（最重要）

必须具体、可操作：

* 实验：
* 写作：
* 技术验证：

（至少3条）

---

## 11. 理论原型（Theory Prototype）（强烈建议）

格式：

理论名称（v0.x）：

* 核心结构：
* 关键变量：
* 系统关系：

---

# 写作约束（必须遵守）

1. 禁止空洞总结，必须结构化表达
2. 优先使用：机制 / 模型 / 系统 / 变量
3. 每一部分必须"可用于论文或实验"
4. "张力"必须落到机制层，不允许停留在描述
5. "行动项"必须真实可执行，不得抽象

---

# 最终目标

这份日报必须同时满足：

* 可以对外发布（具备洞察与结构）
* 可以对内沉淀（可直接转化为）：

  * 论文（related work / discussion）
  * 实验设计
  * 理论框架

---

现在根据以上规范，对输入内容进行完整重写。"""

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
                max_tokens=25000
            )
            return report
        except Exception as e:
            logger.warning(f"  [LLM生成失败]: {e}")
            return self._fallback_report(papers, news)

    def _empty_report(self) -> str:
        """空日报"""
        date = datetime.now().strftime("%Y-%m-%d")
        return f"""# 研究日报 {date}（融合版）

---

## 1. 执行摘要（Executive Summary）

* **核心发现（What changed）**：今日无符合条件的内容
* **为何重要（Why it matters）**：没有新的学术论文或行业新闻通过审查
* **行动启示（What to do）**：请检查数据源和审查标准配置

→ 本日报推进的核心研究问题：Q1 / Q2（待补充）

---

## 2. 本日关键张力（Critical Tensions）

暂无内容。

---

## 3. 深度议题（Research Agenda）

暂无内容。

---

## 4. 方法论角落（Method Corner）

暂无内容。

---

## 5. 核心研究问题（Research Questions）

* Q1：（待补充）
* Q2：（待补充）

---

## 6. 学术论文分析（结构化拆解）

暂无内容。

---

## 7. 行业/新闻分析（结构化）

暂无内容。

---

## 8. 跨域机制映射（Mechanism Mapping）

暂无内容。

---

## 9. 趋势分层（Trend Layers）

* 短期（1年）：（待补充）
* 中期（3年）：（待补充）
* 长期（5–10年）：（待补充）

---

## 10. 可执行行动（Action Items）

* 实验：（待补充）
* 写作：（待补充）
* 技术验证：（待补充）

---

## 11. 理论原型（Theory Prototype）

暂无内容。"""

    def _fallback_report(self, papers: list[dict], news: list[dict]) -> str:
        """降级方案：不使用LLM，直接格式化（中文）"""
        date = datetime.now().strftime("%Y-%m-%d")
        lines = [f"# 研究日报 {date}（融合版）", ""]

        # 执行摘要
        lines.append("---")
        lines.append("")
        lines.append("## 1. 执行摘要（Executive Summary）")
        lines.append("")
        lines.append("* **核心发现（What changed）**：LLM生成失败，使用降级格式输出")
        lines.append("* **为何重要（Why it matters）**：确保日报结构完整")
        lines.append("* **行动启示（What to do）**：建议检查LLM服务状态")
        lines.append("")
        lines.append("→ 本日报推进的核心研究问题：Q1 / Q2（待补充）")
        lines.append("")

        # 论文
        if papers:
            lines.append("---")
            lines.append("")
            lines.append("## 6. 学术论文分析（结构化拆解）")
            lines.append("")
            for p in papers:
                title = p.get("title", "无标题")
                authors = p.get("authors", "未知作者")
                venue = p.get("venue", "")
                doi = p.get("doi", "")
                abstract = p.get("clean_content", "") or p.get("summary", "") or p.get("abstract", "")

                lines.append(f"### [{title}]")
                lines.append(f"1. **核心问题**：（待补充）")
                lines.append(f"2. **方法拆解**：")
                lines.append(f"   * 模型：（待补充）")
                lines.append(f"   * 技术：（待补充）")
                lines.append(f"   * 数据/实验：（待补充）")
                lines.append(f"   * 难点：（待补充）")
                lines.append(f"3. **关键发现**：（待补充）")
                lines.append(f"4. **机制抽象**：（待补充）")
                lines.append(f"5. **对研究问题的意义**：（待补充）")
                lines.append(f"6. **批判性评估**：（待补充）")
                lines.append("")
                lines.append(f"**作者**: {authors}")
                if venue:
                    lines.append(f"**来源**: {venue}")
                if doi:
                    lines.append(f"**DOI**: [{doi}](https://doi.org/{doi})")
                if abstract:
                    lines.append(f"**摘要**: {abstract[:300]}...")
                lines.append("")

        # 新闻
        if news:
            lines.append("---")
            lines.append("")
            lines.append("## 7. 行业/新闻分析（结构化）")
            lines.append("")
            for n in news:
                title = n.get("title", "无标题")
                source = n.get("source", "")
                url = n.get("url", "")
                summary = n.get("clean_content", "") or n.get("summary", "")

                lines.append(f"### [{title}]")
                lines.append(f"* **核心内容**：（待补充）")
                lines.append(f"* **结构分析**：")
                lines.append(f"   * 技术驱动力：（待补充）")
                lines.append(f"   * 经济机制：（待补充）")
                lines.append(f"   * 用户行为变化：（待补充）")
                lines.append(f"* **对研究问题的影响**：（待补充）")
                if source:
                    lines.append(f"* **来源**: {source}")
                if url:
                    lines.append(f"* **链接**: [{url}]({url})")
                lines.append("")

        return "\n".join(lines)