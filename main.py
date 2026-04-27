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
from datetime import datetime
from dotenv import load_dotenv

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
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def main():
    """主工作流"""
    # 加载环境变量
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(env_path)

    # 加载配置
    config = load_config()

    today = datetime.now().strftime("%Y-%m-%d")
    print(f"=" * 60)
    print(f"Daily News Workflow - {today}")
    print(f"=" * 60)

    # ============================================================
    # Phase 1: 收集
    # ============================================================
    print(f"\n[Phase 1] Information Collection")
    print("-" * 40)

    # 收集 Agent 1: 新闻 (RSS + 搜索)
    print("\nCollecting Agent 1: News & Social Media...")
    news_agent = NewsCollectorAgent(config)
    news_items = news_agent.run()

    # 收集 Agent 2: 学术论文
    print("\nCollecting Agent 2: Academic Papers...")
    academic_agent = AcademicCollectorAgent(config)
    paper_items = academic_agent.run()

    # 合并
    all_items = news_items + paper_items
    print(f"\n  Total collected: {len(all_items)} items")
    print(f"    News: {len(news_items)}, Papers: {len(paper_items)}")

    if not all_items:
        print("\nNo items collected. Exiting.")
        return

    # ============================================================
    # Phase 2: 预处理
    # ============================================================
    print(f"\n[Phase 2] Preprocessing")
    print("-" * 40)

    preprocessor = PreprocessorAgent(config)
    processed_items = preprocessor.run(all_items)

    if not processed_items:
        print("\nNo valid items after preprocessing. Exiting.")
        return

    # ============================================================
    # Phase 3: 质量审查
    # ============================================================
    print(f"\n[Phase 3] Quality Review")
    print("-" * 40)

    quality_reviewer = QualityReviewerAgent(config)
    quality_reviewed = quality_reviewer.run(processed_items)

    quality_passed = [item for item in quality_reviewed if item.get("approved", False)]
    print(f"  Quality passed: {len(quality_passed)}/{len(quality_reviewed)}")

    if not quality_passed:
        print("\nNo items passed quality review. Exiting.")
        return

    # ============================================================
    # Phase 4: 相关性审查
    # ============================================================
    print(f"\n[Phase 4] Relevance Review")
    print("-" * 40)

    relevance_reviewer = RelevanceReviewerAgent(config)
    relevance_reviewed = relevance_reviewer.run(quality_passed)

    final_items = [item for item in relevance_reviewed if item.get("approved", False)]
    print(f"  Relevance passed: {len(final_items)}/{len(relevance_reviewed)}")

    if not final_items:
        print("\nNo items passed relevance review. Exiting.")
        return

    # ============================================================
    # Phase 5: 整理输出
    # ============================================================
    print(f"\n[Phase 5] Formatting & Output")
    print("-" * 40)

    formatter = FormatterAgent(config)
    report_content = formatter.run(final_items)

    # ============================================================
    # Phase 6: 写入 Obsidian + 下载 PDF
    # ============================================================
    print(f"\n[Phase 6] Saving to Obsidian")
    print("-" * 40)

    # 确定 vault 路径
    # 优先使用环境变量（GitHub Actions），否则使用配置文件
    vault_path = os.getenv("OBSIDIAN_VAULT_PATH") or config.get("obsidian", {}).get("vault_path", "")
    output_folder = config.get("obsidian", {}).get("output_folder", "Research Feed")
    pdf_folder = config.get("obsidian", {}).get("pdf_folder", "Research Feed/Papers")

    # GitHub Actions 模式：写入项目目录下的 output/ 文件夹
    is_github_actions = os.getenv("GITHUB_ACTIONS") == "true"

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
    print(f"  Daily report saved: {report_path}")

    # 下载论文 PDF
    papers_with_pdf = [
        item for item in final_items
        if item.get("pdf_url") or item.get("doi")
    ]

    if papers_with_pdf and config.get("workflow", {}).get("output", {}).get("include_pdf_download", True):
        pdf_dir = os.path.join(vault_path, pdf_folder)
        downloader = PDFDownloader(pdf_dir)

        print(f"  Downloading {len(papers_with_pdf)} papers...")
        download_results = downloader.download_batch(papers_with_pdf)

        print(f"    Downloaded: {len(download_results['downloaded'])}")
        print(f"    Failed: {len(download_results['failed'])}")

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
            print(f"  Updated report with failed downloads")

        # 下载失败的不再单独写文件，已整合进日报

    # 保存原始数据（调试用）
    debug_path = os.path.join(vault_path, output_folder, f"{today}-raw-data.json")
    os.makedirs(os.path.dirname(debug_path), exist_ok=True)
    with open(debug_path, 'w', encoding='utf-8') as f:
        json.dump(final_items, f, ensure_ascii=False, indent=2)

    # ============================================================
    # 完成
    # ============================================================
    print(f"\n" + "=" * 60)
    print(f"Workflow completed successfully - {today}")
    print(f"  Items collected: {len(all_items)}")
    print(f"  Items preprocessed: {len(processed_items)}")
    print(f"  Quality passed: {len(quality_passed)}")
    print(f"  Relevance passed: {len(final_items)}")
    print(f"  Report: {report_path}")
    print(f"=" * 60)


if __name__ == "__main__":
    main()