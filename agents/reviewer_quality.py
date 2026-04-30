"""
审查 Agent 1: 质量审查
负责过滤低质量内容：广告、垃圾信息、信息不完整等
"""

from tools.llm import get_review_kimi
from tools.json_parser import parse_json
import logging

logger = logging.getLogger(__name__)


class QualityReviewerAgent:
    """质量审查 Agent"""

    SYSTEM_PROMPT = """你是一位质量审查员，负责评估学术和新闻内容的质量，并检测AI生成/虚构内容。

你的任务是评估每条内容是否达到质量标准，识别可能的AI幻觉或编造内容，并返回 JSON 格式的审查结果。

质量标准：
1. 信息完整性：是否有足够实质内容（不是只有标题）
2. 来源可信度：是否来自知名/权威来源
3. 内容性质：是否为新闻/报告，而非观点或软文
4. 语言质量：是否表达清晰、逻辑连贯
5. 内容独特性：是否为实质性内容，而非填充或标题党

评分标准（0.0-1.0）：
- 0.9-1.0：优秀，必须收录
- 0.7-0.9：良好，建议收录
- 0.5-0.7：一般，可选收录
- 0.3-0.5：较差，排除
- 0.0-0.3：极差，坚决排除

## 幻觉检测（必须执行）

对每条内容，额外评估以下幻觉风险指标：

1. **DOI 格式检查**：如果有 DOI，检查是否符合标准格式
   - 期刊 DOI：10.XXXX/xxxxx（如 10.1080/123456）
   - arXiv DOI：10.48550/arXiv.XXXX.XXXXX
   - 格式异常的 DOI -> 标记为高风险

2. **作者-论文对应关系**：检查作者列表是否合理
   - 作者名是否真实人名（非明显乱码或占位符）
   - 作者数量是否合理（单篇论文通常1-20位作者）
   - 如果作者全是 "Unknown" 或明显虚构 -> 标记高风险

3. **标题真实性检查**：检查论文/新闻标题是否像编造的
   - 过于泛泛无具体内容（如仅"Game Research Study"）
   - 措辞自然度（是否有奇怪的语法或机器生成痕迹）
   - 标题是否与来源匹配

4. **内容声称检查**：检查摘要/内容中的声称是否有支撑
   - 是否有具体数据、方法、发现（而非空泛断言）
   - 内容是否与其他来源可交叉验证
   - 纯观点性内容标注但不算幻觉

hallucination_risk 取值：
- "low"：内容可信，各方面检查通过
- "medium"：存在少量疑点但基本可信
- "high"：存在明显幻觉/编造迹象

返回 JSON 数组。每条记录必须包含：
- url: string（原始 URL，用于识别）
- title: string（标题）
- quality_score: float（0.0-1.0）
- approved: boolean（分数 >= 0.5 且 hallucination_risk != "high" 则为 true）
- reason: string（评分简要说明）
- flags: array of strings（如 "clickbait", "advertisement", "incomplete", "opinion"）
- hallucination_risk: string（"low" | "medium" | "high"）
- hallucination_details: string（风险的具体说明，low时可省略）

重要：只返回 JSON 数组，不要解释，不要代码块包裹。严禁编造审查结果——如果无法判断，标记为 "medium" 并说明原因。"""

    def __init__(self, config: dict):
        self.config = config
        self.llm, self.model = get_review_kimi()  # Kimi-2.5 审查

    def run(self, items: list[dict]) -> list[dict]:
        """
        执行质量审查

        Args:
            items: 待审查的条目列表

        Returns:
            审查结果列表（包含 quality_score 和 approved 字段）
        """
        if not items:
            return []

        # 批量审查（每次最多20条，避免token溢出）
        results = []
        batch_size = 20

        logger.info(f"  质量审查 {len(items)} 条内容...")

        for i in range(0, len(items), batch_size):
            batch = items[i:i+batch_size]
            try:
                batch_results = self._review_batch(batch)
                results.extend(batch_results)
                logger.info(f"    批次 {i//batch_size + 1} 完成")
            except Exception as e:
                logger.warning(f"    [批次失败] {e}")
                # 批次失败时，标记为未通过
                for item in batch:
                    item["quality_score"] = 0.0
                    item["approved"] = False
                    item["reason"] = f"Review failed: {e}"
                    results.append(item)

        # 统计
        approved_count = sum(1 for r in results if r.get("approved", False))
        logger.info(f"    审查通过 {approved_count}/{len(results)} 条")

        return results

    def _review_batch(self, batch: list[dict]) -> list[dict]:
        """审查一批内容"""
        # 准备输入数据
        input_items = []
        for item in batch:
            content = item.get("clean_content", "") or item.get("summary", "") or item.get("title", "")
            input_items.append({
                "url": item.get("url", ""),
                "title": item.get("title", ""),
                "source": item.get("source", ""),
                "content_preview": content[:1000]  # 限制长度
            })

        # 调用 LLM
        result = self.llm.chat_json(
            system_prompt=self.SYSTEM_PROMPT,
            user_message=f"请审查以下 {len(input_items)} 条内容，返回 JSON 数组：\n{input_items}",
            model=self.model,
            temperature=0.2
        )

        # 合并结果
        if isinstance(result, list):
            result_map = {r.get("url", ""): r for r in result}

            # 补充原始数据
            for item in batch:
                url = item.get("url", "")
                if url in result_map:
                    reviewed = result_map[url]
                    item["quality_score"] = reviewed.get("quality_score", 0.0)
                    item["approved"] = reviewed.get("approved", False)
                    item["reason"] = reviewed.get("reason", "")
                    item["quality_flags"] = reviewed.get("flags", [])
                    # 幻觉检测字段
                    item["hallucination_risk"] = reviewed.get("hallucination_risk", "low")
                    item["hallucination_details"] = reviewed.get("hallucination_details", "")

                    # 高风险幻觉 -> 强制不通过
                    if item.get("hallucination_risk") == "high":
                        item["approved"] = False
                        detail = item.get("hallucination_details", "检测到AI编造/虚构内容")
                        item["reason"] = (item.get("reason", "") + f" [高风险幻觉: {detail}]")
                else:
                    # 没有对应的审查结果，默认通过
                    item["quality_score"] = 0.5
                    item["approved"] = True
                    item["reason"] = "No review result"
        else:
            # 解析失败，默认全部通过
            for item in batch:
                item["quality_score"] = 0.5
                item["approved"] = True
                item["reason"] = "Parse error"

        return batch
