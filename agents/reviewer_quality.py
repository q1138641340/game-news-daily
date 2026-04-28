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

    SYSTEM_PROMPT = """你是一位质量审查员，负责评估学术和新闻内容的质量。

你的任务是评估每条内容是否达到质量标准，并返回 JSON 格式的审查结果。

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

返回 JSON 数组。每条记录必须包含：
- url: string（原始 URL，用于识别）
- title: string（标题）
- quality_score: float（0.0-1.0）
- approved: boolean（分数 >= 0.5 则为 true）
- reason: string（评分简要说明）
- flags: array of strings（如 "clickbait", "advertisement", "incomplete", "opinion"）

重要：只返回 JSON 数组，不要解释，不要代码块包裹。"""

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
