#!/usr/bin/env python3
"""
Win 端轻量采集脚本 — 只跑 OpenCLI 源（万方/百度学术/小红书）
不重复 GH Actions 已完成的 105 RSS + 学术 API + LLM 审查
"""

import sys, os, time, logging, json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tools.opencli_runner import OpenCLIRunner
from tools.dedup_cache import DedupCache
import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)

    opencli_cfg = config.get("opencli", {})
    if not opencli_cfg.get("enabled", True):
        logger.info("OpenCLI 已禁用，退出")
        return

    runner = OpenCLIRunner(timeout=opencli_cfg.get("timeout_seconds", 90))
    if not runner.is_available():
        logger.warning("OpenCLI 不可用，退出")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    items = []

    # ---- 万方 ----
    wanfang_kw = config.get("academic_keywords", {}).get("wanfang", [])
    for kw in wanfang_kw:
        try:
            results = runner.search_wanfang(kw, max_results=5)
            items.extend(results)
            if results:
                logger.info(f"  [万方] '{kw}': {len(results)} 条")
            time.sleep(10)
        except Exception as e:
            logger.warning(f"  [万方失败] '{kw}': {e}")

    # ---- 百度学术 ----
    baidu_kw = config.get("academic_keywords", {}).get("baidu_scholar", [])
    for kw in baidu_kw:
        try:
            results = runner.search_baidu_scholar(kw, max_results=5)
            items.extend(results)
            if results:
                logger.info(f"  [百度学术] '{kw}': {len(results)} 条")
            time.sleep(8)
        except Exception as e:
            logger.warning(f"  [百度学术失败] '{kw}': {e}")

    # ---- 小红书 ----
    xhs_kw = config.get("xiaohongshu_keywords", [])
    for kw in xhs_kw:
        try:
            results = runner.search_xiaohongshu(kw, max_results=5)
            items.extend(results)
            if results:
                logger.info(f"  [小红书] '{kw}': {len(results)} 条")
            time.sleep(8)
        except Exception as e:
            logger.warning(f"  [小红书失败] '{kw}': {e}")

    if not items:
        logger.info("无 OpenCLI 新内容")
        return

    # ---- 去重 ----
    cache = DedupCache()
    cache_path = os.path.join(os.path.dirname(__file__), "output", ".cache", "seen_items.json")
    if os.path.exists(cache_path):
        cache.load(cache_path)
    fresh, _ = cache.filter_seen(items)
    logger.info(f"去重后: {len(fresh)} 条（共 {len(items)} 条）")

    if not fresh:
        logger.info("去重后无新内容")
        return

    # ---- 输出为补充文件 ----
    output_dir = os.path.join(os.path.dirname(__file__), "output", today)
    os.makedirs(output_dir, exist_ok=True)
    supplement_path = os.path.join(output_dir, "OpenCLI-Supplement.md")

    lines = [
        f"## OpenCLI 补充内容 ({today})",
        "",
        f"> 由 Windows 端在 {datetime.now().strftime('%H:%M')} 自动采集，补充 GitHub Actions 无法抓取的中文源。",
        "",
        f"**万方**: {sum(1 for i in fresh if i.get('source')=='万方')} 篇 | "
        f"**百度学术**: {sum(1 for i in fresh if i.get('source')=='百度学术')} 篇 | "
        f"**小红书**: {sum(1 for i in fresh if i.get('source')=='小红书')} 条",
        "",
        "---",
        ""
    ]

    # 万方/百度学术 → 论文格式
    academic = [i for i in fresh if i.get("source") in ("万方", "百度学术")]
    if academic:
        lines.append("### 中文期刊论文")
        lines.append("")
        for paper in academic:
            lines.append(f"**{paper['title']}**")
            lines.append(f"- 作者: {paper.get('authors', '未知')}")
            if paper.get("venue"):
                lines.append(f"- 来源: {paper['venue']}")
            if paper.get("published_date"):
                lines.append(f"- 日期: {paper['published_date']}")
            if paper.get("url"):
                lines.append(f"- 链接: {paper['url']}")
            lines.append("")

    # 小红书 → 新闻格式
    xhs = [i for i in fresh if i.get("source") == "小红书"]
    if xhs:
        lines.append("### 小红书内容")
        lines.append("")
        for post in xhs:
            author = post.get("author", "?")
            title = post.get("title", "")
            url = post.get("url", "")
            likes = post.get("likes", "")
            date = post.get("date", "")
            lines.append(f"- **{title}** — @{author}  |  {likes}赞  |  {date}")
            if url:
                lines.append(f"  {url}")
            lines.append("")

    with open(supplement_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # 标记去重
    cache.mark_batch_seen(fresh)
    cache.save(cache_path)

    logger.info(f"补充文件已保存: {supplement_path}")
    logger.info(f"总计: {len(fresh)} 条新内容")


if __name__ == "__main__":
    main()
