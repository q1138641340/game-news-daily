#!/usr/bin/env python3
"""
Win 端轻量采集 — 万方/百度学术/小红书 → 存为 pending 数据
GH Actions 在下次运行时 git pull 拉取，进入 LLM 审查流水线
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

    items = []

    # ---- 万方 ----
    for kw in config.get("academic_keywords", {}).get("wanfang", []):
        try:
            results = runner.search_wanfang(kw, max_results=5)
            items.extend(results)
            if results: logger.info(f"  [万方] '{kw}': {len(results)} 条")
            time.sleep(10)
        except Exception as e:
            logger.warning(f"  [万方失败] '{kw}': {e}")

    # ---- 百度学术 ----
    for kw in config.get("academic_keywords", {}).get("baidu_scholar", []):
        try:
            results = runner.search_baidu_scholar(kw, max_results=5)
            items.extend(results)
            if results: logger.info(f"  [百度学术] '{kw}': {len(results)} 条")
            time.sleep(8)
        except Exception as e:
            logger.warning(f"  [百度学术失败] '{kw}': {e}")

    # ---- 小红书 ----
    for kw in config.get("xiaohongshu_keywords", []):
        try:
            results = runner.search_xiaohongshu(kw, max_results=5)
            items.extend(results)
            if results: logger.info(f"  [小红书] '{kw}': {len(results)} 条")
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

    # ---- 存为 pending 数据，等 GH Actions 下次运行时拉取并入审查流水线 ----
    # 不直接改日报，让 GH Actions 的 LLM 审查 + 格式化统一处理
    pending_dir = os.path.join(os.path.dirname(__file__), "output", ".cache")
    os.makedirs(pending_dir, exist_ok=True)
    pending_path = os.path.join(pending_dir, "opencli-pending.json")

    # 读取已有 pending（防止覆盖）
    existing = []
    if os.path.exists(pending_path):
        try:
            with open(pending_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            pass

    # 合并，URL + 标题去重
    seen = {(i.get("url"), i.get("title")) for i in existing}
    for item in fresh:
        key = (item.get("url"), item.get("title"))
        if key not in seen:
            existing.append(item)
            seen.add(key)

    with open(pending_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    cache.mark_batch_seen(fresh)
    cache.save(cache_path)

    logger.info(f"✅ 待处理数据: {pending_path} ({len(existing)} 条)")
    logger.info("   GH Actions 下次运行时会 git pull 这些数据，进入 LLM 审查流程")


if __name__ == "__main__":
    main()
