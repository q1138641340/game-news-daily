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
    """创建空报告"""
    os.makedirs(output_dir, exist_ok=True)
    report_path = os.path.join(output_dir, f"{date}-Daily-Report.md")

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
        # Phase 1: 收集
        # ============================================================
        logger.info("[Phase 1] Information Collection")

        # 收集 Agent 1: 新闻 (RSS + 搜索)
        logger.info("Collecting Agent 1: News & Social Media...")
        news_agent = NewsCollectorAgent(config)
        news_items = news_agent.run()

        # 收集 Agent 2: 学术论文
        logger.info("Collecting Agent 2: Academic Papers...")
        academic_agent = AcademicCollectorAgent(config)
        paper_items = academic_agent.run()

        # 合并
        all_items = news_items + paper_items
        logger.info(f"Total collected: {len(all_items)} items (News: {len(news_items)}, Papers: {len(paper_items)})")

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

        formatter = FormatterAgent(config)
        report_content = formatter.run(final_items)

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

        writer = ObsidianWriter(vault_path, output_folder)

        # 写入日报
        tags = ["daily-report", "game-research"]
        # 添加研究兴趣标签
        for item in final_items:
            for area in item.get("interest_areas", []):
                tag = area.lower().replace(" ", "-")
                if tag not in tags:
                    tags.append(tag)

        report_path = writer.write_daily_report(
            content=report_content,
            date=today,
            tags=tags[:20],  # 限制标签数量
            failed_papers=[]
        )
        logger.info(f"Daily report saved: {report_path}")

        # 下载论文 PDF
        papers_with_pdf = [
            item for item in final_items
            if item.get("pdf_url") or item.get("doi")
        ]

        if papers_with_pdf and config.get("workflow", {}).get("output", {}).get("include_pdf_download", True):
            pdf_dir = os.path.join(vault_path, pdf_folder)
            downloader = PDFDownloader(pdf_dir)

            logger.info(f"Downloading {len(papers_with_pdf)} papers...")
            download_results = downloader.download_batch(papers_with_pdf)

            logger.info(f"Downloaded: {len(download_results['downloaded'])}")
            logger.info(f"Failed: {len(download_results['failed'])}")

            # 如果有下载失败的，更新日报追加失败列表
            if download_results.get("failed"):
                report_content_updated = report_content + writer._format_failed_papers(download_results["failed"], today)
                # 覆盖写入（带 failed_papers）
                writer.write_daily_report(
                    content=report_content_updated,
                    date=today,
                    tags=tags[:20],
                    failed_papers=download_results["failed"]
                )
                logger.info("Updated report with failed downloads")

        # 保存原始数据（调试用）
        debug_path = os.path.join(vault_path, output_folder, f"{today}-raw-data.json")
        os.makedirs(os.path.dirname(debug_path), exist_ok=True)
        with open(debug_path, 'w', encoding='utf-8') as f:
            json.dump(final_items, f, ensure_ascii=False, indent=2)

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
            os.makedirs(output_dir, exist_ok=True)
            error_path = os.path.join(output_dir, f"{today}-ERROR.md")
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
