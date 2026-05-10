#!/usr/bin/env python3
"""
周论文生成脚本
每周日 12:00 UTC (北京时间 20:00) 运行
"""

import os
import sys
import glob
import argparse
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.paper_generator import PaperGeneratorAgent
from tools.citation_tracker import CitationTracker
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def collect_weekly_reports(vault_path: str, days: int = 7) -> list[dict]:
    """
    从 vault 中收集过去N天的日报

    Args:
        vault_path: Obsidian vault 路径
        days: 收集的天数

    Returns:
        list[dict]: 日报列表
    """
    reports = []
    research_feed = os.path.join(vault_path, "Research Feed")

    if not os.path.exists(research_feed):
        logger.error(f"Research Feed 目录不存在: {research_feed}")
        return reports

    # 计算日期范围
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    logger.info(f"收集 {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')} 的日报")

    tracker = CitationTracker()

    # 遍历日期文件夹
    for i in range(days):
        date = start_date + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        date_folder = os.path.join(research_feed, date_str)

        if not os.path.exists(date_folder):
            logger.warning(f"日期文件夹不存在: {date_folder}")
            continue

        report_file = os.path.join(date_folder, "Daily-Report.md")
        if not os.path.exists(report_file):
            logger.warning(f"日报文件不存在: {report_file}")
            continue

        # 读取日报内容
        with open(report_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 从 Markdown 中提取参考文献
        extracted_refs = tracker.extract_from_markdown(content, date_str)

        # 解析日报结构
        parsed = parse_daily_report(content)

        # 组装报告数据
        report = {
            "date": date_str,
            "content": content,
            "academic_papers": [r for r in extracted_refs if r.get("type") == "paper"],
            "industry_news": [r for r in extracted_refs if r.get("type") == "news"],
            "executive_summary": parsed.get("executive_summary", ""),
            "strategic_enhancements": parsed.get("strategic_enhancements", {}),
        }

        reports.append(report)
        logger.info(f"  已收集: {date_str} ({len(report['academic_papers'])} papers, {len(report['industry_news'])} news)")

    return reports


def parse_daily_report(content: str) -> dict:
    """
    解析日报内容，提取各模块

    Args:
        content: 日报 Markdown 内容

    Returns:
        dict: 解析后的日报数据
    """
    report = {
        "academic_papers": [],
        "industry_news": [],
        "executive_summary": "",
        "strategic_enhancements": {}
    }

    lines = content.split('\n')
    current_section = None

    for line in lines:
        # 检测模块
        if '## 执行摘要' in line or '## 研究日报' in line:
            current_section = "summary"
        elif '## 学术论文' in line:
            current_section = "papers"
        elif '## 行业新闻' in line or '## 行业动态' in line:
            current_section = "news"
        elif '## 战略增强' in line or '**以下为战略增强内容**' in line:
            current_section = "enhancements"

        # 根据当前模块处理内容
        if current_section == "summary" and line.strip() and not line.startswith('#'):
            report["executive_summary"] += line.strip() + " "

        # 简化处理：收集所有论文和新闻
        # 完整实现需要更复杂的解析逻辑

    report["executive_summary"] = report["executive_summary"].strip()
    return report


def save_paper(paper: str, output_dir: str, date_range: str) -> str:
    """
    保存论文到文件

    Args:
        paper: 论文 Markdown 内容
        output_dir: 输出目录
        date_range: 日期范围

    Returns:
        str: 保存的文件路径
    """
    os.makedirs(output_dir, exist_ok=True)

    # 生成文件名：YYYY-WXX-标题.md
    today = datetime.now()
    week_num = today.isocalendar()[1]

    # 提取标题（第一个 # 后的内容）
    title = "未命名"
    for line in paper.split('\n'):
        if line.startswith('# ') and len(line) > 3:
            title = line[2:].strip()[:30]  # 最多30字
            title = "".join(c if c.isalnum() or c in (' ', '-', '_') else '' for c in title)
            title = title.replace(' ', '-')
            break

    filename = f"{today.strftime('%Y')}-W{week_num:02d}-{title}.md"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(paper)

    logger.info(f"周论文已保存: {filepath}")
    return filepath


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='生成周论文')
    parser.add_argument('--test', action='store_true', help='测试模式')
    parser.add_argument('--days', type=int, default=7, help='收集的天数')
    parser.add_argument('--vault', type=str, help='Obsidian vault 路径')
    args = parser.parse_args()

    # 加载环境变量
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
        logger.info("已加载 .env 文件")

    # 确定 vault 路径
    vault_path = args.vault or os.getenv("OBSIDIAN_VAULT_PATH", "")
    if not vault_path:
        # 默认路径
        vault_path = "/Users/sunjinghe/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian Vault/game-news-daily"

    logger.info(f"Vault 路径: {vault_path}")

    # 确定输出路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "output", "weekly_papers")

    if args.test:
        # 测试模式：使用最近的日报
        logger.info("=== 测试模式 ===")

        # 查找最近的日报
        research_feed = os.path.join(vault_path, "Research Feed")
        if os.path.exists(research_feed):
            # 获取所有日期文件夹并排序
            date_folders = sorted(glob.glob(os.path.join(research_feed, "2026-*")))
            if date_folders:
                # 取最后7个
                recent_folders = date_folders[-min(args.days, len(date_folders)):]
                reports = []
                for folder in recent_folders:
                    date_str = os.path.basename(folder)
                    report_file = os.path.join(folder, "Daily-Report.md")
                    if os.path.exists(report_file):
                        with open(report_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                        parsed = parse_daily_report(content)
                        parsed["date"] = date_str
                        reports.append(parsed)
                        logger.info(f"  测试数据: {date_str}")

                if reports:
                    # 生成论文
                    generator = PaperGeneratorAgent()
                    paper = generator.generate_weekly(reports)

                    # 保存
                    date_range = f"{reports[0]['date']} 至 {reports[-1]['date']}"
                    filepath = save_paper(paper, output_dir, date_range)
                    logger.info(f"\n=== 测试完成 ===")
                    logger.info(f"论文已保存到: {filepath}")
                    return

        logger.warning("没有找到测试数据")
        return

    # 正式运行模式
    logger.info("=== 周论文生成开始 ===")

    # 收集日报
    reports = collect_weekly_reports(vault_path, args.days)

    if not reports:
        logger.error("没有收集到日报数据")
        sys.exit(1)

    logger.info(f"已收集 {len(reports)} 天的日报")

    # ---- 引用验证 ----
    logger.info("=== 引用验证 ===")
    from tools.citation_verifier import verify_batch
    import yaml
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    all_refs = []
    for report in reports:
        all_refs.extend(report.get("academic_papers", []))
        all_refs.extend(report.get("industry_news", []))
    if all_refs:
        logger.info(f"  验证 {len(all_refs)} 条引用...")
        all_refs = verify_batch(all_refs)
        # 回写验证结果到 reports
        verified_count = sum(1 for r in all_refs if r.get("verified"))
        logger.info(f"  验证通过: {verified_count}/{len(all_refs)}")

    # ---- 生成 Research Cards ----
    logger.info("=== 生成 Research Cards ===")
    from tools.research_card import cards_from_reports, format_cards_for_writing
    cards = cards_from_reports(reports, config)
    writable = [c for c in cards if c.is_writable]
    logger.info(f"  可写卡片: {len(writable)}/{len(cards)}")
    cards_text = format_cards_for_writing(cards)

    # 生成论文
    generator = PaperGeneratorAgent()
    paper = generator.generate_weekly(reports, cards_text=cards_text)

    # 保存
    date_range = f"{reports[0]['date']} 至 {reports[-1]['date']}"
    filepath = save_paper(paper, output_dir, date_range)

    logger.info(f"\n=== 周论文生成完成 ===")
    logger.info(f"日期范围: {date_range}")
    logger.info(f"保存位置: {filepath}")


if __name__ == "__main__":
    main()
