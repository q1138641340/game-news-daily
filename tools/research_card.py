"""
Research Card System — 所有信息在进入写作层前的结构化冻结层
每一张 card 代表一条经过验证、可追溯的研究碎片
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class ResearchCard:
    """研究碎片卡片 — 写作模型只能引用这些，禁止自由生成 citation"""
    id: str                          # "paper_20260510_001" / "news_20260510_001"
    title: str                       # 论文/新闻标题
    source: str                      # arXiv / CrossRef / GamesIndustry / ...
    date: str                        # YYYY-MM-DD
    verified: bool = False           # citation_verifier 验证结果
    summary: str = ""                # 2-3 句关键摘要
    key_claims: list[str] = field(default_factory=list)  # 核心观点
    quotes: list[str] = field(default_factory=list)      # 关键引述
    entities: list[str] = field(default_factory=list)    # 人物/公司/产品名
    tags: list[str] = field(default_factory=list)        # 分类标签
    url: str = ""
    doi: str = ""
    confidence_score: float = 0.0    # 0.0-1.0，由 source_trust + verification 综合
    verification_detail: str = ""    # 验证结果的文字说明

    @property
    def is_writable(self) -> bool:
        """是否允许进入写作层（confidence >= 0.4 或已验证）"""
        return self.verified or self.confidence_score >= 0.4


def _build_card_id(prefix: str, date: str, index: int) -> str:
    """生成卡片 ID，如 paper_20260510_003"""
    safe_date = date.replace("-", "") if date else datetime.now().strftime("%Y%m%d")
    return f"{prefix}_{safe_date}_{index:03d}"


def cards_from_report(report: dict, config: dict = None) -> list[ResearchCard]:
    """
    从单天日报中提取所有论文和新闻转为 ResearchCard。

    Args:
        report: {"date": "2026-05-08", "academic_papers": [...], "industry_news": [...]}
        config: 全局配置（用于 source_trust 查表）

    Returns:
        list[ResearchCard]
    """
    date = report.get("date", "")
    cards = []
    trust_map = _build_trust_map(config)

    # 学术论文 → cards
    for i, paper in enumerate(report.get("academic_papers", []), 1):
        source = paper.get("source", paper.get("venue", "unknown"))
        base_confidence = trust_map.get(source.lower(), 0.5)

        card = ResearchCard(
            id=_build_card_id("paper", date, i),
            title=paper.get("title", ""),
            source=source,
            date=paper.get("date", paper.get("published_date", date)),
            verified=paper.get("verified", False),
            summary=paper.get("abstract", "")[:500],
            url=paper.get("url", ""),
            doi=paper.get("doi", ""),
            confidence_score=paper.get("confidence_score", base_confidence),
            verification_detail=paper.get("verification_detail", ""),
            tags=[t for t in [paper.get("category", ""), paper.get("type", "")] if t],
        )
        cards.append(card)

    # 行业新闻 → cards
    for i, news in enumerate(report.get("industry_news", []), 1):
        source = news.get("source", "unknown")
        base_confidence = trust_map.get(source.lower(), 0.5)

        card = ResearchCard(
            id=_build_card_id("news", date, i),
            title=news.get("title", ""),
            source=source,
            date=news.get("date", date),
            verified=news.get("verified", False),
            summary=news.get("summary", "")[:500],
            url=news.get("url", ""),
            doi=news.get("doi", ""),
            confidence_score=news.get("confidence_score", base_confidence),
            verification_detail=news.get("verification_detail", ""),
            tags=[t for t in [news.get("category", ""), news.get("type", "")] if t],
        )
        cards.append(card)

    return cards


def cards_from_reports(daily_reports: list[dict], config: dict = None) -> list[ResearchCard]:
    """跨多天日报批量提取 cards"""
    all_cards = []
    for report in daily_reports:
        cards = cards_from_report(report, config)
        all_cards.extend(cards)
    logger.info(f"  [Research Cards] 共生成 {len(all_cards)} 张卡片")
    return all_cards


def format_cards_for_writing(cards: list[ResearchCard], max_cards: int = 40) -> str:
    """
    将 cards 格式化为写作模型的输入。
    只包含 is_writable 的 cards，按 confidence 排序取前 N 张。
    """
    writable = [c for c in cards if c.is_writable]
    writable.sort(key=lambda c: c.confidence_score, reverse=True)
    writable = writable[:max_cards]

    if not writable:
        return "（无可用研究卡片）"

    parts = []
    for c in writable:
        ver = f"[{'✅' if c.verified else '⚠'}]" if c.confidence_score >= 0.5 else "[❌]"
        parts.append(
            f"{ver} **[{c.id}] {c.title}**\n"
            f"   Source: {c.source} | Date: {c.date} | Confidence: {c.confidence_score:.0%}\n"
            f"   Summary: {c.summary or '(no summary)'}\n"
            f"   URL: {c.url} | DOI: {c.doi}\n"
        )

    return "\n".join(parts)


def _build_trust_map(config: dict = None) -> dict[str, float]:
    """从 config 构建 source → base_confidence 映射"""
    if not config:
        config = {}

    source_trust = config.get("source_trust", {})
    trust_map = {}

    for source in source_trust.get("high", []):
        trust_map[source.lower()] = 0.85
    for source in source_trust.get("medium", []):
        trust_map[source.lower()] = 0.65
    for source in source_trust.get("low", []):
        trust_map[source.lower()] = 0.35

    return trust_map
