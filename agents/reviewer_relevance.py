"""
审查 Agent 2: 相关性审查
负责评估内容与用户研究兴趣的相关性
"""

from tools.llm import get_review_glm
from tools.json_parser import parse_json
import logging

logger = logging.getLogger(__name__)


class RelevanceReviewerAgent:
    """相关性审查 Agent"""

    SYSTEM_PROMPT = """你是一位相关性审查员，专注于游戏研究与跨媒体艺术领域。

## 用户的核心研究兴趣

### 第一优先级（直接相关，必须收录）：
- 游戏研究（游戏学/ludology、游戏叙事、交互式叙事）
- 媒介理论与批评（数字媒介、电子游戏作为媒介、媒介考古学）
- 游戏技术哲学（程序修辞、具身交互、控制论与游戏）
- 游戏叙事学（分支叙事、环境叙事、跨媒体叙事）
- 交互式文学/文献学（电子文学、互动小说、数字文本）
- 媒介艺术史（游戏史、数字艺术史、控制论史）
- 游戏中的人工智能（NPC行为、叙事生成、程序化叙事）

### 第二优先级（间接相关，值得收录）：
- 游戏开发（引擎、工具、GDC、行业报告、年度数据）
- 游戏与人机交互（UX研究、玩家体验）
- 虚拟现实/增强现实（作为叙事与交互媒介）
- 数字人文（与游戏/交互媒体相关的）
- 计算/程序化内容生成（PCG）在游戏中的应用
- 计算机图形学（仅限与游戏渲染、实时交互直接相关的，每批最多4篇）

### 严格排除领域（与用户兴趣无关，直接标记 approved=false）：
- 纯经济学：授权策略、网络外部性、定价模型、博弈论应用（除非直接涉及游戏产业经济）
- 纯教育技术：GIS实验教学、课程设计、教学方法、在线教育平台（除非涉及严肃游戏/游戏化学习）
- 纯医学/临床研究
- 纯数学/理论物理（除非与游戏开发直接相关）
- 纯语言学/NLP（除非涉及叙事理解、故事生成）
- 行政管理/公共政策
- 社会学/人类学（除非涉及游戏文化研究）

## 图形学/理工科论文配额规则

对于计算机图形学、计算几何、编译器优化等纯技术论文：
- 每批最多通过 4 篇
- 仅保留与游戏/交互体验最直接相关的（如游戏渲染、实时图形、VR/AR相关）
- 超出配额的标记 approved=false

## 缺失领域提醒

以下领域如果完全没有出现，请在 reason 中标注"【缺失领域提醒】：建议补充 [领域名] 相关内容"：
- 媒介艺术史/游戏史
- 控制论史/系统论
- 交互式文学/电子文学
- 媒介考古学

## 评分标准

- 0.9-1.0：直接触及第一优先级核心研究兴趣
- 0.7-0.9：与第一优先级高度相关
- 0.5-0.7：与第二优先级相关，或间接关联第一优先级
- 0.3-0.5：边缘相关，需谨慎判断
- 0.0-0.3：属于排除领域或完全无关

## 评分原则（重要！必须遵循）

### 排除原则
- **经济学论文（授权策略、网络外部性等）→ 0.0-0.2，approved=false**
- **教育技术论文（GIS实验、课程设计等）→ 0.0-0.2，approved=false**
- **纯理论数学/物理（无游戏应用）→ 0.0-0.2，approved=false**
- **医学/临床研究 → 0.0，approved=false**

### 通过原则
- 第一优先级内容：默认 >= 0.6
- 第二优先级内容：根据具体关联度给 0.4-0.7
- 图形学论文：最多通过 4 篇/批次，超出标记 approved=false
- **与游戏、数字媒体、交互、AI、叙事有任何关系的论文 → >= 0.3**
- **arXiv 论文如果涉及 AI、交互、VR、叙事 → 默认 >= 0.5**
- **CrossRef 中与媒体、文化、数字人文相关 → 默认 >= 0.5**

### 不通过原则
- **"网络外部性下的最优授权策略"类经济学论文 → 不通过**
- **"GIS实验教学"类教育技术论文 → 不通过**
- **纯计算几何、编译器优化等无游戏关联 → 不通过或低分**

## 评分理由要求

每条评分必须在 reason 字段中说明：
1. 为什么这篇论文相关或不相关
2. 它与用户研究兴趣的具体联系
3. 如果是不通过，说明具体原因（如"属于纯经济学研究，与游戏研究无关"）

返回 JSON 数组。每条记录必须包含：
- url: string
- title: string
- relevance_score: float（0.0-1.0）
- priority: string（"high", "medium", "low"）
- approved: boolean（分数 >= 0.3 且不属于排除领域才为 true）
- interest_areas: array of strings（关联的具体研究领域）
- reason: string（评分理由，必须说明为什么相关或不相关）
- needs_verification: boolean
- verification_sources: array of strings

重要：只返回 JSON 数组，不要解释，不要代码块包裹。"""

    def __init__(self, config: dict):
        self.config = config
        self.llm, self.model = get_review_glm()  # Kimi-2.5 审查

    def run(self, items: list[dict]) -> list[dict]:
        """
        执行相关性审查

        Args:
            items: 通过质量审查的条目列表

        Returns:
            添加了相关性评分的条目列表
        """
        if not items:
            return []

        # 只审查通过质量审查的条目
        quality_passed = [item for item in items if item.get("approved", False)]

        if not quality_passed:
            return []

        logger.info(f"  相关性审查 {len(quality_passed)} 条内容...")

        # 统计图形学类论文
        cs_graphics_count = sum(
            1 for item in quality_passed
            if self._is_cs_graphics(item)
        )
        logger.info(f"    [图形学/理工类论文: {cs_graphics_count} 条，配额: 最多4条/批次]")

        # 批量审查
        results = []
        batch_size = 15  # 减少批次大小，更精细控制

        for i in range(0, len(quality_passed), batch_size):
            batch = quality_passed[i:i+batch_size]
            try:
                batch_results = self._review_batch(batch, cs_graphics_count)
                results.extend(batch_results)
                logger.info(f"    批次 {i//batch_size + 1} 完成")
            except Exception as e:
                logger.warning(f"    [批次失败] {e}")
                for item in batch:
                    item["relevance_score"] = 0.5
                    item["approved"] = True
                    item["priority"] = "medium"
                    results.append(item)

        # 统计
        approved = [r for r in results if r.get("approved", False)]
        high = sum(1 for r in approved if r.get("priority") == "high")
        medium = sum(1 for r in approved if r.get("priority") == "medium")
        low = sum(1 for r in approved if r.get("priority") == "low")
        rejected = sum(1 for r in results if not r.get("approved", False))

        logger.info(f"    通过: {len(approved)} 条 (high:{high} medium:{medium} low:{low}) | 排除: {rejected} 条")

        return results

    def _is_cs_graphics(self, item: dict) -> bool:
        """判断是否是计算机图形学/理工类论文"""
        title = item.get("title", "").lower()
        abstract = item.get("abstract", "").lower()
        content = (item.get("clean_content", "") or "").lower()
        venue = item.get("venue", "").lower()

        graphics_keywords = [
            "graphics", "rendering", "ray tracing", "mesh", "polygon",
            "shader", "voxel", "geometry", "geometric", "computational geometry",
            "nvidia", "amd", "vulkan", "directx", "opengl",
            "simulation", "fluid", "cloth", "physics based"
        ]

        combined = f"{title} {abstract} {venue}"

        # 检查是否是图形学相关
        is_graphics = any(kw in combined for kw in graphics_keywords)

        # 检查是否与游戏直接相关
        game_related = any(
            kw in combined
            for kw in ["game", "video game", "interactive", "vr", "ar", "virtual reality"]
        )

        return is_graphics and not game_related

    def _review_batch(self, batch: list[dict], cs_graphics_total: int) -> list[dict]:
        """审查一批内容"""
        input_items = []
        for item in batch:
            content = item.get("clean_content", "") or item.get("summary", "") or item.get("title", "")
            input_items.append({
                "url": item.get("url", ""),
                "title": item.get("title", ""),
                "source": item.get("source", ""),
                "venue": item.get("venue", ""),
                "content_preview": content[:800]
            })

        result = self.llm.chat_json(
            system_prompt=self.SYSTEM_PROMPT,
            user_message=f"请评估以下内容与用户研究兴趣的相关性，返回 JSON 数组：\n{input_items}",
            model=self.model,
            temperature=0.2
        )

        if isinstance(result, list):
            result_map = {r.get("url", ""): r for r in result}

            for item in batch:
                url = item.get("url", "")
                if url in result_map:
                    reviewed = result_map[url]
                    item["relevance_score"] = reviewed.get("relevance_score", 0.0)
                    item["priority"] = reviewed.get("priority", "low")
                    item["approved"] = reviewed.get("approved", False)
                    item["interest_areas"] = reviewed.get("interest_areas", [])
                    item["reason"] = reviewed.get("reason", "")
                    item["needs_verification"] = reviewed.get("needs_verification", False)
                    item["verification_sources"] = reviewed.get("verification_sources", [])
                else:
                    item["relevance_score"] = 0.5
                    item["priority"] = "medium"
                    item["approved"] = True
                    item["interest_areas"] = []
                    item["reason"] = "No review result"
                    item["needs_verification"] = False
        else:
            for item in batch:
                item["relevance_score"] = 0.5
                item["priority"] = "medium"
                item["approved"] = True
                item["interest_areas"] = []
                item["reason"] = "Parse error"
                item["needs_verification"] = False

        # 图形学论文配额检查
        graphics_approved = [
            item for item in batch
            if item.get("approved", False) and self._is_cs_graphics(item)
        ]

        if len(graphics_approved) > 4:
            # 保留评分最高的4篇，其余标记为不通过
            graphics_approved.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
            for item in graphics_approved[4:]:
                item["approved"] = False
                item["reason"] = item.get("reason", "") + " [超出图形学配额]"
                logger.info(f"    [排除] 图形学配额超限: {item.get('title', '')[:40]}...")

        return batch
