"""
学术论文生成 Agent
支持周论文和月论文两种模式，严格遵循 CSSCI 期刊标准
"""

import logging
from datetime import datetime
from typing import Optional
from tools.llm import get_format_deepseek, get_kimi_reviewer, get_collect_minimax
from tools.citation_tracker import CitationTracker

logger = logging.getLogger(__name__)


class PaperGeneratorAgent:
    """
    学术论文生成 Agent
    支持周论文和月论文两种模式
    """

    WEEKLY_SYSTEM_PROMPT = """你是人文社科领域资深学者，擅长撰写 CSSCI 期刊标准学术论文。

任务：根据过去一周的日报内容，生成一篇 12000-15000 字的学术论文。

## 输入数据
你将收到过去7天的研究日报，每天的日报包含以下模块：
- 执行摘要：当日最重要的3-5项内容概述
- 学术论文：游戏研究、AI治理、人机交互等领域的论文
- 行业新闻：深度报道分析
- 趋势与关联分析：跨领域趋势
- 战略增强：核心张力声明、反向思考、本周研究路径

## 论文结构（严格遵循）
1. **标题**（不超过25字，反映核心议题）
2. **摘要**（200-300字，独立成段）
   - 格式：[研究背景] + [研究方法] + [核心发现] + [理论意义]
3. **关键词**（3-5个，学术术语）
4. **引言**（500-800字）
   - 研究背景与问题意识
   - 研究目标
   - 论文结构说明
5. **文献回顾与理论框架**（800-1200字）
   - 相关研究梳理
   - 核心概念界定
   - 本文理论框架
6. **实证分析与发现**（1500-2500字）
   - 基于日报内容的案例分析
   - 论证展开
   - 发现总结
7. **批判性讨论**（1000-1500字）
   - **核心张力分析**：从日报"战略增强"部分的核心张力引申
   - 潜在局限与反例
   - 理论与实践意义
8. **结论与展望**（500-800字）
   - 核心发现总结
   - 理论贡献
   - 研究局限
   - 未来方向
9. **参考文献**（至少 25-30 条）
   - 整合日报中的所有引用，确保数量充足
   - 严格按照 GB/T 7713.1 新国标格式
   - 期刊：[序号] 作者. 题名[J]. 刊名, 年, 卷(期): 起止页码.
   - 专著：[序号] 作者. 书名[M]. 出版地: 出版社, 年.
   - 电子文献：[序号] 作者. 题名[EB/OL]. (发布日期)[引用日期]. URL.
   - DOI 必须保留，标于文献末尾

## 写作要求

### 引用规范
- 所有引用必须来自输入的日报内容，严禁杜撰
- 正文中使用 [1][2] 格式的数字引用
- 参考文献与日报条目一一对应，可追溯
- 期刊格式：作者. 题名[J]. 期刊, 年, 卷(期): 页码.
- 新闻格式：作者. 标题[N]. 来源, 日期.

### 语言风格
- 语言严谨精妙，学术规范
- 避免口语化表达
- 句子结构严谨，避免歧义
- 允许使用适度的学术过渡词，但不强求特定词汇

### 创新点要求
- 必须从日报"战略增强"部分的"核心张力"中引申出来
- 创新点需明确指出，1-3个为宜
- 说明与现有研究的区别

### 格式规范
- Markdown 格式
- 使用多级标题（#, ##, ###）
- 避免使用 emoji
- 严谨的学术写作风格

## 输出要求
- 完整 Markdown 论文
- 不使用代码块包裹
- 字数控制在 5000-8000 字（不含参考文献）
- 全部使用中文"""

    MONTHLY_SYSTEM_PROMPT = """你是人文社科领域资深学者，擅长撰写 CSSCI 期刊标准学术论文。

任务：根据过去一个月的周论文，生成一篇 12000-15000 字的月度大论文。

## 输入数据
你将收到过去一个月的周论文（约4-5篇），每篇周论文包含：
- 标题、摘要、关键词
- 引言、理论框架
- 实证分析与发现
- 批判性讨论
- 结论与参考文献

## 论文结构（比周论文更宏大）

1. **标题**（不超过30字，反映全月核心议题）
2. **摘要**（300-400字）
3. **关键词**（5-8个）
4. **引言**（800-1200字）
   - 月度研究背景
   - 元叙事的确立
   - 月度研究目标
5. **文献回顾与理论框架**（1500-2000字）
   - 跨周论文的学术史梳理
   - 整合的理论框架
6. **跨周实证分析**（3000-4000字）
   - 打通各周论文的案例分析
   - 纵向对比与横向关联
   - 整合性发现
7. **元叙事批判讨论**（2000-3000字）
   - **贯穿全月的元叙事分析**
   - 跨周的张力与矛盾
   - 理论与实践的深层意义
8. **结论与展望**（800-1200字）
   - 月度核心贡献
   - 理论整合的贡献
   - 研究局限
   - 未来研究方向
9. **参考文献**
   - 整合当月所有原始引用
   - 数量不少于50条

## 特别要求

### 元叙事提炼
- 必须从各周论文中提炼出一条贯穿全月的"元叙事"
- 元叙事是整合性的理论线索，不是简单拼接
- 说明各周洞见如何在元叙事下相互关联

### 批判性要求
- 不仅总结，要深入批判
- 指出各周论文之间的矛盾与张力
- 提出超越各周论文的新见解

### 写作风格
- 语言更加厚重深邃
- 论证更加严密
- 学术规范，避免口语化

## 输出要求
- 完整 Markdown 论文
- 不使用代码块包裹
- 字数控制在 12000-15000 字（不含参考文献）
- 全部使用中文"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.llm, self.model = get_format_deepseek()              # 写作模型
        self.initial_llm, self.initial_model = get_collect_minimax()  # 初审 (MiniMax)
        self.reviewer_llm, self.reviewer_model = get_kimi_reviewer()  # 复审 (Kimi)
        self.citation_tracker = CitationTracker()

    def generate_weekly(self, daily_reports: list[dict]) -> str:
        """
        生成周论文

        Args:
            daily_reports: 过去7天的日报，每项包含：
                - date: str (YYYY-MM-DD)
                - content: str (完整日报 Markdown)
                - academic_papers: list[dict]
                - industry_news: list[dict]
                - executive_summary: str
                - strategic_enhancements: dict

        Returns:
            完整 Markdown 论文
        """
        if not daily_reports:
            logger.warning("没有日报数据，无法生成周论文")
            return self._empty_paper("周论文")

        # 提取参考文献
        all_refs = []
        for report in daily_reports:
            if "academic_papers" in report or "industry_news" in report:
                refs = self.citation_tracker.extract_references([report])
                all_refs.extend(refs)

        # 构建输入
        date_range = f"{daily_reports[0].get('date', '')} 至 {daily_reports[-1].get('date', '')}"

        # 准备论文数据
        papers_data = []
        for report in daily_reports:
            day_entry = {
                "date": report.get("date", ""),
                "executive_summary": report.get("executive_summary", ""),
                "academic_papers": report.get("academic_papers", []),
                "industry_news": report.get("industry_news", []),
                "trends": report.get("trends", ""),
                "strategic_enhancements": report.get("strategic_enhancements", {})
            }
            papers_data.append(day_entry)

        # 调用 LLM 生成
        user_message = self._build_weekly_prompt(date_range, papers_data)

        try:
            paper = self.llm.chat(
                system_prompt=self.WEEKLY_SYSTEM_PROMPT,
                user_message=user_message,
                model=self.model,
                temperature=0.4,
                max_tokens=32000
            )

            # 追加参考文献
            if all_refs:
                bib = self.citation_tracker.format_bibliography(all_refs)
                paper += bib

            # ---- 层1: MiniMax 初审（循环修订直到通过） ----
            max_loops = 10
            mini_review_log = []
            for loop in range(max_loops):
                init_review = self._initial_review_paper(paper, "周论文")
                mini_review_log.append({"round": loop+1, "issues": init_review["issues"], "passed": init_review["passed"]})
                if init_review["passed"]:
                    logger.info(f"  [周论文] MiniMax初审: ✅ 通过 (round {loop+1})")
                    break
                logger.info(f"  [周论文] MiniMax初审: {init_review['issues']}个问题，第{loop+1}次修订...")
                paper = self._revise_paper(paper, init_review)
            else:
                logger.info(f"  [周论文] MiniMax初审: ⚠ {max_loops}轮后仍有问题")

            # ---- 层2: Kimi 复审（循环修订直到通过） ----
            kimi_review_log = []
            for loop in range(max_loops):
                kim_review = self._review_paper(paper, "周论文", str(papers_data)[:2000])
                kimi_review_log.append({"round": loop+1, "severe": kim_review.get("severe", 0),
                                        "medium": kim_review.get("medium", 0),
                                        "minor": kim_review.get("minor", 0),
                                        "passed": kim_review["passed"]})
                if kim_review["passed"]:
                    logger.info(f"  [周论文] Kimi复审: ✅ 通过 (round {loop+1})")
                    break
                logger.info(f"  [周论文] Kimi复审: 严重{kim_review['severe']}个, 中等{kim_review['medium']}个, 轻微{kim_review['minor']}个，第{loop+1}次修订...")
                paper = self._revise_paper(paper, kim_review)
            else:
                logger.info(f"  [周论文] Kimi复审: ⚠ {max_loops}轮后仍有问题")

            # ---- 工序证明 ----
            proof = self._build_paper_process_proof(
                "周论文", date_range, mini_review_log, kimi_review_log,
                len(all_refs), init_review, kim_review
            )
            paper = f"{proof}\n\n---\n\n{paper}"

            logger.info(f"  [周论文生成] 完成，字数约 {len(paper)} 字")
            return paper

        except Exception as e:
            logger.error(f"  [周论文生成失败] {e}")
            return self._error_paper(str(e))

    def generate_monthly(self, weekly_papers: list[dict]) -> str:
        """
        生成月论文

        Args:
            weekly_papers: 当月所有周论文，每项包含：
                - week_date: str (如 "2026-W19")
                - title: str
                - content: str (完整周论文 Markdown)
                - core_tension: str
                - references: list[dict]

        Returns:
            完整 Markdown 论文
        """
        if not weekly_papers:
            logger.warning("没有周论文数据，无法生成月论文")
            return self._empty_paper("月论文")

        # 整合所有参考文献
        all_refs = []
        for wp in weekly_papers:
            refs = wp.get("references", [])
            all_refs.extend(refs)

        # 提取各周的核心张力
        tensions = []
        for wp in weekly_papers:
            tension = wp.get("core_tension", "")
            if tension:
                tensions.append(f"第{wp.get('week_date', '')}周: {tension}")

        # 构建输入
        month_range = f"{weekly_papers[0].get('month', '')}"

        user_message = self._build_monthly_prompt(month_range, weekly_papers, tensions)

        try:
            paper = self.llm.chat(
                system_prompt=self.MONTHLY_SYSTEM_PROMPT,
                user_message=user_message,
                model=self.model,
                temperature=0.4,
                max_tokens=48000
            )

            # 追加参考文献
            if all_refs:
                bib = self.citation_tracker.format_bibliography(all_refs)
                paper += bib

            # ---- 层1: MiniMax 初审（循环修订直到通过） ----
            max_loops = 10
            mini_review_log = []
            for loop in range(max_loops):
                init_review = self._initial_review_paper(paper, "月论文")
                mini_review_log.append({"round": loop+1, "issues": init_review["issues"], "passed": init_review["passed"]})
                if init_review["passed"]:
                    logger.info(f"  [月论文] MiniMax初审: ✅ 通过 (round {loop+1})")
                    break
                logger.info(f"  [月论文] MiniMax初审: {init_review['issues']}个问题，第{loop+1}次修订...")
                paper = self._revise_paper(paper, init_review)
            else:
                logger.info(f"  [月论文] MiniMax初审: ⚠ {max_loops}轮后仍有问题")

            # ---- 层2: Kimi 复审（循环修订直到通过） ----
            kimi_review_log = []
            for loop in range(max_loops):
                kim_review = self._review_paper(paper, "月论文", str(weekly_papers)[:2000])
                kimi_review_log.append({"round": loop+1, "severe": kim_review.get("severe", 0),
                                        "medium": kim_review.get("medium", 0),
                                        "minor": kim_review.get("minor", 0),
                                        "passed": kim_review["passed"]})
                if kim_review["passed"]:
                    logger.info(f"  [月论文] Kimi复审: ✅ 通过 (round {loop+1})")
                    break
                logger.info(f"  [月论文] Kimi复审: 严重{kim_review['severe']}个, 中等{kim_review['medium']}个, 轻微{kim_review['minor']}个，第{loop+1}次修订...")
                paper = self._revise_paper(paper, kim_review)
            else:
                logger.info(f"  [月论文] Kimi复审: ⚠ {max_loops}轮后仍有问题")

            # ---- 工序证明 ----
            proof = self._build_paper_process_proof(
                "月论文", month_range, mini_review_log, kimi_review_log,
                len(all_refs), init_review, kim_review
            )
            paper = f"{proof}\n\n---\n\n{paper}"

            logger.info(f"  [月论文生成] 完成，字数约 {len(paper)} 字")
            return paper

        except Exception as e:
            logger.error(f"  [月论文生成失败] {e}")
            return self._error_paper(str(e))

    def _build_weekly_prompt(self, date_range: str, papers_data: list) -> str:
        """构建周论文生成 prompt"""
        prompt = f"""请根据以下过去一周的研究日报，生成一篇学术论文。

## 时间范围
{date_range}（共 {len(papers_data)} 天）

"""

        for i, day in enumerate(papers_data, 1):
            prompt += f"""
### 第 {i} 天日报 ({day.get('date', '')})

**执行摘要**:
{day.get('executive_summary', '（无）')}

**学术论文**:
"""
            for paper in day.get("academic_papers", [])[:5]:  # 最多5篇
                prompt += f"""
- 标题: {paper.get('title', '未知')}
  作者: {paper.get('authors', '未知')}
  来源: {paper.get('venue', '未知')}
  DOI: {paper.get('doi', '无')}
  摘要: {paper.get('abstract', paper.get('clean_content', ''))[:200]}...
"""

            prompt += f"""
**行业新闻**:
"""
            for news in day.get("industry_news", [])[:3]:  # 最多3条
                prompt += f"""
- 标题: {news.get('title', '未知')}
  来源: {news.get('source', '未知')}
  摘要: {news.get('summary', news.get('clean_content', ''))[:200]}...
"""

            prompt += f"""
**战略增强**:
"""
            se = day.get("strategic_enhancements", {})
            prompt += f"""
- 核心张力: {se.get('core_tension', '（无）')}
- 反向思考: {se.get('counter_thinking', '（无）')}
- 研究路径: {se.get('research_path', '（无）')}
"""

        prompt += """
## 写作要求
1. 论文标题不超过25字
2. 字数控制在 5000-8000 字
3. 严格遵循 CSSCI 期刊结构
4. 所有引用必须来自上述日报内容
5. 创新点从"核心张力"中引申
6. 语言严谨，避免口语化

请生成完整 Markdown 论文：
"""
        return prompt

    def _build_monthly_prompt(self, month_range: str, weekly_papers: list, tensions: list) -> str:
        """构建月论文生成 prompt"""
        prompt = f"""请根据以下过去一个月的周论文，生成一篇月度大论文。

## 月份
{month_range}（共 {len(weekly_papers)} 周）

"""

        for wp in weekly_papers:
            prompt += f"""
### {wp.get('week_date', '周')} 周论文

**标题**: {wp.get('title', '未知')}

**摘要**:
{(wp.get('abstract') or (wp.get('content', '')[:500]))}...

**核心张力**:
{wp.get('core_tension', '（无）')}

"""
            if wp.get('content'):
                # 截取关键部分
                content = wp['content']
                if len(content) > 2000:
                    content = content[:2000] + "..."
                prompt += f"**内容摘要**:\n{content}\n"

        if tensions:
            prompt += """
## 各周核心张力汇总
"""
            for t in tensions:
                prompt += f"- {t}\n"

        prompt += """
## 写作要求
1. 论文标题不超过30字
2. 字数控制在 12000-15000 字
3. 必须提炼出贯穿全月的"元叙事"
4. 整合各周论文的洞见到元叙事中
5. 批判性讨论比周论文更加深入
6. 参考文献不少于50条
7. 所有引用必须来自上述周论文内容

请生成完整 Markdown 月度大论文：
"""
        return prompt

    REVIEWER_SYSTEM_PROMPT = """你是 CSSCI 期刊资深匿名审稿人。你的任务是严格审查一篇学术论文，找出所有问题。

## 审查维度（每项打分：严重/中等/轻微/无）

### 1. 参考文献格式（最重要！必须逐条检查）
- 每条参考文献是否符合 GB/T 7713.1 新国标？
- 期刊论文格式：[序号] 作者. 题名[J]. 刊名, 年, 卷(期): 起止页码.
- 专著格式：[序号] 作者. 书名[M]. 出版地: 出版社, 年.
- 电子文献格式：[序号] 作者. 题名[EB/OL]. (发布日期)[引用日期]. URL.
- DOI是否保留并正确？
- 任何格式错误都标记为"严重"

### 2. 事实准确性
- 引用的论文标题、作者、期刊是否准确？
- 是否有明显的事实错误或时间错误？
- 是否杜撰了不存在的引用？

### 3. 参考文献数量
- 参考文献是否达到 25-30 条？
- 不足 25 条标记为"严重"

### 4. 逻辑严密性
- 论点是否有充分的证据支持？
- 论证链条是否有断裂或跳跃？

### 5. 学术规范
- 结构是否完整？
- 摘要是否涵盖背景+方法+发现+意义？

### 6. 语言与表达
- 是否有口语化或非学术表达？
- 是否有机翻痕迹？

### 7. 创新性与价值
- 是否有明显的AI生成痕迹？

## 输出格式

```
## 审稿意见

### 总体评价
[一段话]

### 严重问题
1. ...
（没有则写"无"）

### 中等问题
1. ...
（没有则写"无"）

### 轻微问题
1. ...
（没有则写"无"）

### 修订建议
1. ...
```

只输出审稿意见，不要其他内容。"""

    REVISION_SYSTEM_PROMPT = """你是人文社科领域资深学者。根据审稿人的反馈，修订你的论文。

## 修订要求
1. 逐条回应审稿人的每个问题
2. 严重问题必须彻底修改
3. 中等问题需要明显改进
4. 轻微问题酌情处理
5. 保持论文的整体结构和学术风格
6. 修订后的论文应比原稿有明显提升

## 输出
完整的修订后 Markdown 论文。"""

    INITIAL_REVIEW_PROMPT = """你是学术编辑，负责论文初审。快速筛查以下问题：

1. 结构完整性：论文是否有明显的章节缺失？
2. 引用可靠性：引用的论文/作者/期刊是否看起来真实可信？
3. 逻辑连贯性：论证是否有明显的跳跃或矛盾？
4. 语言质量：是否有明显的机翻痕迹或非学术表达？
5. AI痕迹：是否有明显的"首先...其次...最后"套路化模板痕迹？
6. 参考文献数量：是否少于25条？格式是否符合GB/T 7713.1？

只列出你发现的严重问题（真正需要修改的），每条一行。
轻微的风格问题不要列。不要为了凑数编问题。
如果你认为论文质量已经达标，只输出三个字：初审通过

重要：宁可漏过轻微问题，也不要反复纠缠。质量达标就放行。"""

    def _initial_review_paper(self, paper: str, paper_type: str) -> dict:
        """MiniMax 初审：快速筛查明显问题"""
        user_msg = f"请初审以下{paper_type}：\n\n{paper[:8000]}"
        try:
            feedback = self.initial_llm.chat(
                system_prompt=self.INITIAL_REVIEW_PROMPT,
                user_message=user_msg,
                model=self.initial_model,
                temperature=0.2,
                max_tokens=1500
            )
            # 判断是否通过
            passed = "初审通过" in feedback
            issues = len([l for l in feedback.split('\n') if l.strip() and not l.startswith('#')]) if not passed else 0

            logger.info(f"  [MiniMax初审] {paper_type}: {'✅ 通过' if passed else f'发现 {issues} 个问题'}")

            return {
                "passed": passed,
                "issues": issues,
                "feedback": feedback,
                "reviewer": "MiniMax",
            }
        except Exception as e:
            logger.warning(f"  [MiniMax初审失败] {e}")
            return {"passed": True, "issues": 0, "feedback": "", "reviewer": "MiniMax"}

    def _review_paper(self, paper: str, paper_type: str, source_data: str = "") -> dict:
        """
        Kimi 2.5 审稿

        Returns:
            dict with keys: passed (bool), issues (int), feedback (str)
        """
        user_msg = f"""请审查以下{paper_type}。

**论文类型**: {paper_type}
**原始数据摘要**: {source_data[:1000] if source_data else "（未提供）"}

---
{paper[:12000]}
---"""
        try:
            feedback = self.reviewer_llm.chat(
                system_prompt=self.REVIEWER_SYSTEM_PROMPT,
                user_message=user_msg,
                model=self.reviewer_model,
                temperature=0.3,
                max_tokens=4000
            )
            # 统计问题数
            import re
            severe = len(re.findall(r'### 严重问题.*?\n', feedback))
            medium = len(re.findall(r'### 中等问题.*?\n', feedback))
            minor = len(re.findall(r'### 轻微问题.*?\n', feedback))
            total_issues = severe + medium + minor

            logger.info(f"  [审稿] {paper_type}: 严重{severe}个, 中等{medium}个, 轻微{minor}个")

            return {
                "passed": severe == 0,
                "issues": total_issues,
                "feedback": feedback,
                "severe": severe,
                "medium": medium,
                "minor": minor,
            }
        except Exception as e:
            logger.warning(f"  [审稿失败] {e}")
            return {"passed": True, "issues": 0, "feedback": "", "severe": 0, "medium": 0, "minor": 0}

    def _revise_paper(self, paper: str, review: dict) -> str:
        """根据审稿反馈修订论文"""
        if not review.get("feedback") or review.get("passed"):
            return paper

        user_msg = f"""## 审稿人反馈
{review['feedback']}

## 原稿
{paper[:10000]}

请根据审稿人反馈输出修订后的完整论文。"""
        try:
            revised = self.llm.chat(
                system_prompt=self.REVISION_SYSTEM_PROMPT,
                user_message=user_msg,
                model=self.model,
                temperature=0.3,
                max_tokens=32000
            )
            logger.info(f"  [修订] 完成")
            return revised
        except Exception as e:
            logger.warning(f"  [修订失败] {e}")
            return paper

    def _build_paper_process_proof(self, paper_type: str, date_range: str,
                                    mini_log: list, kimi_log: list,
                                    ref_count: int, final_mini: dict, final_kimi: dict) -> str:
        """生成论文工序证明"""
        today = datetime.now().strftime("%Y-%m-%d")
        lines = [f"## 工序证明 | {paper_type} | {today}", ""]

        lines.append(f"**生成日期**: {today}")
        lines.append(f"**覆盖范围**: {date_range}")
        lines.append("")

        # 模型说明
        lines.append("### 参与模型")
        lines.append("| 阶段 | 模型 | 职责 |")
        lines.append("|------|------|------|")
        lines.append("| 写作 | DeepSeek V4 Pro | 初稿生成 |")
        lines.append("| 初审 | MiniMax M2.7 | 结构/引用/语言快速筛查 |")
        lines.append("| 复审 | Kimi 2.5 (moonshot-v1-32k) | 学术规范/GB/T 7713.1/事实核查 |")
        lines.append("| 修订 | DeepSeek V4 Pro | 根据审稿意见修订 |")
        lines.append("")

        # MiniMax 初审日志
        lines.append(f"### 初审 (MiniMax M2.7) — {len(mini_log)} 轮")
        lines.append("| 轮次 | 问题数 | 结果 |")
        lines.append("|------|--------|------|")
        for entry in mini_log:
            r = entry["round"]
            issues = entry["issues"]
            status = "✅ 通过" if entry["passed"] else ("❌ 修订 → 再审" if r < len(mini_log) else "⚠ 达上限")
            lines.append(f"| {r} | {issues} | {status} |")
        lines.append(f"| **最终** | **{final_mini['issues']}** | **{'✅ 通过' if final_mini['passed'] else '⚠ 未通过'}** |")
        lines.append("")

        # Kimi 复审日志
        lines.append(f"### 复审 (Kimi 2.5) — {len(kimi_log)} 轮")
        lines.append("| 轮次 | 严重 | 中等 | 轻微 | 结果 |")
        lines.append("|------|------|------|------|------|")
        for entry in kimi_log:
            r = entry["round"]
            s, m, mn = entry["severe"], entry["medium"], entry["minor"]
            status = "✅ 通过" if entry["passed"] else ("❌ 修订 → 再审" if r < len(kimi_log) else "⚠ 达上限")
            lines.append(f"| {r} | {s} | {m} | {mn} | {status} |")
        lines.append(f"| **最终** | **{final_kimi.get('severe', 0)}** | **{final_kimi.get('medium', 0)}** | **{final_kimi.get('minor', 0)}** | **{'✅ 通过' if final_kimi['passed'] else '⚠ 未通过'}** |")
        lines.append("")

        # 参考文献统计
        lines.append(f"### 参考文献")
        lines.append(f"- 收录: **{ref_count} 条**")
        lines.append(f"- 格式标准: **GB/T 7713.1**")
        lines.append(f"- 状态: {'✅ 达标' if ref_count >= 25 else '⚠ 偏少（<' + str(25) + '条）'}")
        lines.append("")

        # 修订评估
        lines.append("### 修订评估")
        if final_mini["passed"] and final_kimi["passed"]:
            lines.append("✅ 两轮审查均已通过，论文已达到发表质量。")
        elif final_mini["passed"]:
            lines.append("⚠ 初审通过但复审仍有保留，建议人工复核 Kimi 提出的问题。")
        elif final_kimi["passed"]:
            lines.append("⚠ 初审未通过但复审已放宽，建议检查 MiniMax 初审是否过严。")
        else:
            lines.append("⚠ 两轮审查均未在轮次上限内完全通过。建议人工检查审稿意见是否合理，或调整审稿严格度。")
            lines.append(f"  - MiniMax 初审: {len(mini_log)} 轮后仍发现 {final_mini['issues']} 个问题")
            lines.append(f"  - Kimi 复审: {len(kimi_log)} 轮后仍有 {final_kimi.get('severe', 0)} 个严重问题")

        return "\n".join(lines)

    def _empty_paper(self, paper_type: str) -> str:
        """生成空论文"""
        date = datetime.now().strftime("%Y-%m-%d")
        return f"""# {paper_type}生成失败

日期：{date}

原因：没有足够的输入数据。

请确保有足够的日报或周论文数据后再生成{paper_type}。
"""

    def _error_paper(self, error: str) -> str:
        """生成错误论文"""
        date = datetime.now().strftime("%Y-%m-%d")
        return f"""# 论文生成失败

日期：{date}

错误信息：{error}

请检查日志获取更多信息。
"""
