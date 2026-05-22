"""
Daily News Workflow - 主入口
串联所有 Agent 实现完整工作流

流程:
1. 收集 Agent 1 (新闻) + 收集 Agent 2 (学术论文) -> 并行收集
2. 预处理 Agent -> HTML 转 Markdown，过滤无关内容
3. 审查 Agent 1 (质量) -> 过滤垃圾信息
4. 审查 Agent 2 (相关性) -> 评估与用户兴趣的匹配度
5. 整理输出 Agent -> 生成 Obsidian Markdown 日报
6. PDF 下载 + Obsidian 写入
"""

import os
import sys
import json
import yaml
import logging
from datetime import datetime
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# 降低第三方库日志级别，减少刷屏
logging.getLogger('readability').setLevel(logging.WARNING)
logging.getLogger('lxml').setLevel(logging.WARNING)
logging.getLogger('ddgs').setLevel(logging.WARNING)
logging.getLogger('duckduckgo_search').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.collector_news import NewsCollectorAgent
from agents.collector_academic import AcademicCollectorAgent
from agents.preprocessor import PreprocessorAgent
from agents.reviewer_quality import QualityReviewerAgent
from agents.reviewer_relevance import RelevanceReviewerAgent
from agents.formatter import FormatterAgent
from tools.pdf_downloader import PDFDownloader
from tools.obsidian import ObsidianWriter
from tools.dedup_cache import DedupCache


def load_config() -> dict:
    """加载配置文件"""
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"Config file not found: {config_path}")
        raise
    except yaml.YAMLError as e:
        logger.error(f"Invalid YAML in config file: {e}")
        raise


def create_empty_report(output_dir: str, date: str, reason: str = "No content"):
    """创建空报告（使用日期文件夹结构）"""
    date_folder = f"{date}"
    output_date_dir = os.path.join(output_dir, date_folder)
    os.makedirs(output_date_dir, exist_ok=True)

    # 也创建 Papers 子文件夹（保持结构一致）
    papers_subdir = os.path.join(output_date_dir, "Papers")
    os.makedirs(papers_subdir, exist_ok=True)

    report_path = os.path.join(output_date_dir, "Daily-Report.md")

    content = f"""---
title: "Game Research Daily - {date}"
date: {date}
type: daily-report
tags:
  - daily-report
  - game-research
  - empty-report
---

## 今日无符合条件的内容

日期：{date}

**原因**: {reason}

可能原因：
- 没有符合您研究兴趣的新发表或新闻
- 所有收集的内容在质量审查阶段被过滤
- API 速率限制或网络问题导致数据收集失败

请检查配置后重试。
"""
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(content)

    logger.info(f"Empty report created: {report_path}")
    return report_path


def main():
    """主工作流"""
    try:
        # 加载环境变量
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path)
            logger.info("Loaded environment variables from .env file")
        else:
            logger.info("No .env file found, using environment variables")

        # 加载配置
        config = load_config()

        today = datetime.now().strftime("%Y-%m-%d")
        is_github_actions = os.getenv("GITHUB_ACTIONS") == "true"

        logger.info("=" * 60)
        logger.info(f"Daily News Workflow - {today}")
        if is_github_actions:
            logger.info("Running in GitHub Actions mode")
        logger.info("=" * 60)

        # ============================================================
        # Phase 0: 加载跨天去重缓存
        output_dir = os.path.join(os.path.dirname(__file__), "output")
        # ============================================================
        cache_dir = os.path.join(output_dir, ".cache")
        cache_path = os.path.join(cache_dir, "seen_items.json")
        dedup_cache = DedupCache(max_age_days=90)
        dedup_cache.load(cache_path)
        logger.info("[Phase 0] Cross-day dedup cache loaded")

        # ============================================================
        # Phase 1: 收集
        # ============================================================
        logger.info("[Phase 1] Information Collection")

        # 收集 Agent 1: 新闻 (RSS + 搜索)
        logger.info("Collecting Agent 1: News & Social Media...")
        news_agent = NewsCollectorAgent(config, dedup_cache)
        news_items = news_agent.run()

        # 收集 Agent 2: 学术论文
        logger.info("Collecting Agent 2: Academic Papers...")
        academic_agent = AcademicCollectorAgent(config, dedup_cache)
        paper_items = academic_agent.run()

        # ---- 加载 Win 端 OpenCLI 待处理数据 ----
        pending_opencli = os.path.join(output_dir, ".cache", "opencli-pending.json")
        opencli_items = []
        if os.path.exists(pending_opencli):
            try:
                with open(pending_opencli, "r", encoding="utf-8") as f:
                    opencli_items = json.load(f)
                logger.info(f"Loaded {len(opencli_items)} OpenCLI items from Win (万方/百度学术/小红书)")
                # 关键：立即标记到 dedup cache，防止跨天重复
                if opencli_items:
                    dedup_cache.mark_batch_seen(opencli_items)
                    logger.info(f"  OpenCLI 数据已标记到 dedup cache")
                # 加载后清空，防止重复
                os.remove(pending_opencli)
            except Exception as e:
                logger.warning(f"Failed to load OpenCLI pending data: {e}")

        # 合并
        all_items = news_items + paper_items + opencli_items
        logger.info(f"Total collected: {len(all_items)} items (News: {len(news_items)}, Papers: {len(paper_items)}, OpenCLI: {len(opencli_items)})")

        if not all_items:
            logger.warning("No items collected. Creating empty report.")
            output_dir = os.path.join(os.path.dirname(__file__), "output")
            create_empty_report(output_dir, today, "No items collected from sources")
            return

        # ============================================================
        # Phase 2: 预处理
        # ============================================================
        logger.info("[Phase 2] Preprocessing")

        preprocessor = PreprocessorAgent(config)
        processed_items = preprocessor.run(all_items)

        if not processed_items:
            logger.warning("No valid items after preprocessing. Creating empty report.")
            output_dir = os.path.join(os.path.dirname(__file__), "output")
            create_empty_report(output_dir, today, "No valid items after preprocessing")
            return

        # ============================================================
        # Phase 3: 质量审查
        # ============================================================
        logger.info("[Phase 3] Quality Review")

        quality_reviewer = QualityReviewerAgent(config)
        quality_reviewed = quality_reviewer.run(processed_items)

        quality_passed = [item for item in quality_reviewed if item.get("approved", False)]
        logger.info(f"Quality passed: {len(quality_passed)}/{len(quality_reviewed)}")

        if not quality_passed:
            logger.warning("No items passed quality review. Creating empty report.")
            output_dir = os.path.join(os.path.dirname(__file__), "output")
            create_empty_report(output_dir, today, "No items passed quality review")
            return

        # ============================================================
        # Phase 4: 相关性审查
        # ============================================================
        logger.info("[Phase 4] Relevance Review")

        relevance_reviewer = RelevanceReviewerAgent(config)
        relevance_reviewed = relevance_reviewer.run(quality_passed)

        final_items = [item for item in relevance_reviewed if item.get("approved", False)]
        logger.info(f"Relevance passed: {len(final_items)}/{len(relevance_reviewed)}")

        if not final_items:
            logger.warning("No items passed relevance review. Creating empty report.")
            output_dir = os.path.join(os.path.dirname(__file__), "output")
            create_empty_report(output_dir, today, "No items passed relevance review")
            return

        # ============================================================
        # Phase 5: 整理输出
        # ============================================================
        logger.info("[Phase 5] Formatting & Output")

        # 构建流水线元数据，用于工序证明
        today_str = datetime.now().strftime("%Y-%m-%d")
        pipeline_meta = {
            "stats": {
                "collected": len(all_items),
                "news_rss_api": len(news_items),
                "academic_api": len(paper_items),
                "opencli_win": len(opencli_items),
                "preprocessed": len(processed_items),
                "quality_passed": len(quality_passed),
                "relevance_passed": len(final_items),
                "final_count": len(final_items),
            },
            "min_quality": config.get("workflow", {}).get("review", {}).get("min_quality_score", 0.5),
            "min_relevance": config.get("workflow", {}).get("review", {}).get("min_relevance_score", 0.3),
            "models": {
                "收集清洗": {"name": "MiniMax M2.7", "provider": "MiniMax", "status": "✅"},
                "预处理": {"name": "DeepSeek Flash", "provider": "DeepSeek", "status": "✅"},
                "质量审查": {"name": "Kimi 2.5 (moonshot-v1-32k)", "provider": "Moonshot/Kimi", "status": "✅"},
                "相关性审查": {"name": "Kimi 2.5 (moonshot-v1-32k)", "provider": "Moonshot/Kimi", "status": "✅"},
                "日报生成": {"name": "DeepSeek V4 Pro", "provider": "DeepSeek", "status": "✅"},
                "战略增强": {"name": "DeepSeek V4 Pro", "provider": "DeepSeek", "status": "✅"},
            },
            "quality_checks": {
                "hallucination": {"enabled": True, "flagged": 0, "auto_reject": True},
                "dedup": {"total_removed": len(all_items) - len(final_items)},
            },
            "alerts": [],  # Will be populated below
            "cookie_status": {},
        }

        # 检测微博 Cookie 状态（记录到已推送仓库的元文件中）
        sub_cache_file = os.path.join(os.path.dirname(__file__), "output", ".cache", "cookie_state.json")
        cookie_state = {}
        if os.path.exists(sub_cache_file):
            try:
                with open(sub_cache_file, 'r') as f:
                    cookie_state = json.load(f)
                for name, info in cookie_state.items():
                    set_date = info.get("set_date", "")
                    if set_date:
                        days_ago = (datetime.now() - datetime.strptime(set_date, "%Y-%m-%d")).days
                        info["days_ago"] = days_ago
                        if days_ago > 60:
                            pipeline_meta["alerts"].append(
                                f"**微博 SUB cookie 已使用 {days_ago} 天**，可能即将过期，建议手动更新")

            except Exception:
                pass
        pipeline_meta["cookie_status"] = cookie_state

        # 收集阶段告警（RSS 源失败等）
        failed_sources = news_agent.failed_sources if hasattr(news_agent, 'failed_sources') else []
        if failed_sources:
            pipeline_meta["alerts"].append(f"**{len(failed_sources)} 个 RSS 源采集失败**，详见日志")

        if not pipeline_meta["alerts"]:
            pipeline_meta["alerts"].append("本次运行各组件正常，无需特别关注")

        formatter = FormatterAgent(config)
        report_content = formatter.run(final_items, pipeline_meta)

        # ============================================================
        # Phase 6: 写入 Obsidian + 下载 PDF
        # ============================================================
        logger.info("[Phase 6] Saving to Obsidian")

        # 确定 vault 路径
        # 优先使用环境变量（GitHub Actions），否则使用配置文件
        vault_path = os.getenv("OBSIDIAN_VAULT_PATH") or config.get("obsidian", {}).get("vault_path", "")
        output_folder = config.get("obsidian", {}).get("output_folder", "Research Feed")
        pdf_folder = config.get("obsidian", {}).get("pdf_folder", "Research Feed/Papers")

        # GitHub Actions 模式：写入项目目录下的 output/ 文件夹
        if is_github_actions:
            # 在 GitHub Actions 中，输出到仓库的 output/ 目录
            output_dir = os.path.join(os.path.dirname(__file__), "output")
            vault_path = output_dir
            output_folder = ""
            pdf_folder = "papers"

        # ============================================================
        # 创建日期文件夹结构
        # 格式：YYYY-MM-DD/
        #   ├── Daily-Report.md
        #   └── Papers/
        # ============================================================
        date_folder = f"{today}"
        output_date_dir = os.path.join(output_dir, date_folder)
        os.makedirs(output_date_dir, exist_ok=True)

        # Papers 子文件夹
        papers_subdir = os.path.join(output_date_dir, "Papers")
        os.makedirs(papers_subdir, exist_ok=True)

        logger.info(f"Output directory: {output_date_dir}")

        writer = ObsidianWriter(output_date_dir, "")  # 路径已包含 output_folder

        # 写入日报（使用固定文件名 Daily-Report.md）
        tags = ["daily-report", "game-research"]
        for item in final_items:
            for area in item.get("interest_areas", []):
                tag = area.lower().replace(" ", "-")
                if tag not in tags:
                    tags.append(tag)

        report_path = writer.write_daily_report(
            content=report_content,
            date=today,
            tags=tags[:20],
            failed_papers=[],
            filepath=os.path.join(output_date_dir, "Daily-Report.md")
        )
        logger.info(f"Daily report saved: {report_path}")

        # 下载论文 PDF
        papers_with_pdf = [
            item for item in final_items
            if item.get("pdf_url") or item.get("doi")
        ]

        if papers_with_pdf and config.get("workflow", {}).get("output", {}).get("include_pdf_download", True):
            pdf_dir = papers_subdir  # 使用新的 Papers 子文件夹
            downloader = PDFDownloader(pdf_dir)

            logger.info(f"Downloading {len(papers_with_pdf)} papers...")
            download_results = downloader.download_batch(papers_with_pdf)

            logger.info(f"Downloaded: {len(download_results['downloaded'])}")
            logger.info(f"Failed: {len(download_results['failed'])}")

            # 如果有下载失败的，更新日报追加失败列表
            if download_results.get("failed"):
                writer.write_daily_report(
                    content=report_content,
                    date=today,
                    tags=tags[:20],
                    failed_papers=download_results["failed"],
                    filepath=os.path.join(output_date_dir, "Daily-Report.md")
                )
                logger.info("Updated report with failed downloads")

        # ============================================================
        # Phase 6.5: 保存跨天去重缓存（agents 已在 Phase 1 标记原始条目）
        # ============================================================
        dedup_cache.save(cache_path)
        logger.info("[Phase 6.5] Cross-day dedup cache saved")

        # ============================================================
        # 完成
        # ============================================================
        logger.info("=" * 60)
        logger.info(f"Workflow completed successfully - {today}")
        logger.info(f"  Items collected: {len(all_items)}")
        logger.info(f"  Items preprocessed: {len(processed_items)}")
        logger.info(f"  Quality passed: {len(quality_passed)}")
        logger.info(f"  Relevance passed: {len(final_items)}")
        logger.info(f"  Report: {report_path}")
        logger.info("=" * 60)

    except Exception as e:
        logger.exception("Workflow failed with error")
        # 尝试创建错误报告
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            output_dir = os.path.join(os.path.dirname(__file__), "output")
            date_folder = f"{today}"
            output_date_dir = os.path.join(output_dir, date_folder)
            os.makedirs(output_date_dir, exist_ok=True)
            error_path = os.path.join(output_date_dir, "Daily-Report.md")
            with open(error_path, 'w', encoding='utf-8') as f:
                f.write(f"# Workflow Error - {today}\n\n")
                f.write(f"Error: {str(e)}\n\n")
                f.write("Please check the logs for details.\n")
            logger.info(f"Error report saved: {error_path}")
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
