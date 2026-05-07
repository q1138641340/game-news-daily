#!/usr/bin/env python3
"""
月论文生成脚本
每月最后一天运行
"""

import os
import sys
import glob
import argparse
from datetime import datetime
from dotenv import load_dotenv

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.paper_generator import PaperGeneratorAgent
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def collect_weekly_papers(vault_path: str, year: int, month: int) -> list[dict]:
    """
    从 vault 中收集当月所有周论文

    Args:
        vault_path: Obsidian vault 路径
        year: 年份
        month: 月份

    Returns:
        list[dict]: 周论文列表
    """
    papers = []
    weekly_papers_dir = os.path.join(vault_path, "Research Feed", "Weekly Papers")

    if not os.path.exists(weekly_papers_dir):
        logger.error(f"Weekly Papers 目录不存在: {weekly_papers_dir}")
        return papers

    # 月份格式
    month_str = f"{year}-{month:02d}"
    month_prefixes = [
        f"{year}-W",  # 标准格式如 2026-W19
    ]

    logger.info(f"收集 {year} 年 {month} 月的周论文")

    # 获取所有周论文
    all_papers = glob.glob(os.path.join(weekly_papers_dir, "*.md"))

    for paper_path in all_papers:
        filename = os.path.basename(paper_path)

        # 检查是否属于当月
        # 格式: YYYY-WXX-Title.md
        is_current_month = False
        for prefix in month_prefixes:
            if filename.startswith(prefix):
                # 进一步检查月份
                # 从文件名提取 WXX 部分
                if 'W' in filename:
                    is_current_month = True
                    break

        if not is_current_month:
            continue

        # 读取内容
        with open(paper_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 解析周论文
        paper = {
            "filename": filename,
            "content": content,
            "title": "",
            "abstract": "",
            "core_tension": "",
            "references": []
        }

        # 提取标题
        for line in content.split('\n'):
            if line.startswith('# ') and len(line) > 2:
                paper["title"] = line[2:].strip()
                break

        # 提取摘要
        abstract_start = content.find('**摘要**')
        if abstract_start != -1:
            abstract_end = content.find('\n\n', abstract_start)
            if abstract_end == -1:
                abstract_end = content.find('\n##', abstract_start)
            if abstract_end != -1:
                paper["abstract"] = content[abstract_start:abstract_end].strip()

        # 提取核心张力
        tension_keywords = ['核心张力', '结构性张力', '最核心的']
        for keyword in tension_keywords:
            tension_pos = content.find(keyword)
            if tension_pos != -1:
                tension_end = content.find('\n', tension_pos)
                if tension_end != -1:
                    paper["core_tension"] = content[tension_pos:tension_end].strip()
                    break

        # 提取引用
        refs = []
        ref_pattern = r'\[(\d+)\]\s+(.+?)(?:\n|$)'
        import re
        for match in re.finditer(ref_pattern, content):
            refs.append({
                "id": int(match.group(1)),
                "text": match.group(2).strip()
            })
        paper["references"] = refs

        papers.append(paper)
        logger.info(f"  已收集: {filename}")

    # 按文件名排序
    papers.sort(key=lambda x: x["filename"])

    return papers


def save_paper(paper: str, output_dir: str, year: int, month: int) -> str:
    """
    保存论文到文件

    Args:
        paper: 论文 Markdown 内容
        output_dir: 输出目录
        year: 年份
        month: 月份

    Returns:
        str: 保存的文件路径
    """
    os.makedirs(output_dir, exist_ok=True)

    # 生成文件名：YYYY-MMM-Title.md
    month_names = [
        "", "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    month_name = month_names[month]

    # 提取标题
    title = "未命名"
    for line in paper.split('\n'):
        if line.startswith('# ') and len(line) > 3:
            title = line[2:].strip()[:30]
            title = "".join(c if c.isalnum() or c in (' ', '-', '_') else '' for c in title)
            title = title.replace(' ', '-')
            break

    filename = f"{year}-{month_name}-{title}.md"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(paper)

    logger.info(f"月论文已保存: {filepath}")
    return filepath


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='生成月论文')
    parser.add_argument('--test', action='store_true', help='测试模式')
    parser.add_argument('--year', type=int, help='年份')
    parser.add_argument('--month', type=int, help='月份')
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
        vault_path = "/Users/sunjinghe/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian Vault/game-news-daily"

    logger.info(f"Vault 路径: {vault_path}")

    # 确定输出路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "output", "monthly_papers")

    # 确定年月
    today = datetime.utcnow()
    year = args.year or today.year
    month = args.month or today.month

    if args.test:
        # 测试模式：使用所有可用的周论文
        logger.info("=== 测试模式 ===")
        papers = collect_weekly_papers(vault_path, year, month)

        if not papers:
            logger.warning("没有找到周论文数据")
            return

        logger.info(f"已收集 {len(papers)} 篇周论文")

        # 生成论文
        generator = PaperGeneratorAgent()
        paper = generator.generate_monthly(papers)

        # 保存
        filepath = save_paper(paper, output_dir, year, month)
        logger.info(f"\n=== 测试完成 ===")
        logger.info(f"论文已保存到: {filepath}")
        return

    # 检查是否是月末
    next_day = datetime(year, month, 28)
    import datetime as dt
    next_day = next_day + dt.timedelta(days=4)
    if next_day.month == month:
        logger.info(f"{year} 年 {month} 月不是月末，跳过月论文生成")
        sys.exit(0)

    # 正式运行模式
    logger.info(f"=== 月论文生成开始 ===")
    logger.info(f"月份: {year} 年 {month} 月")

    # 收集周论文
    papers = collect_weekly_papers(vault_path, year, month)

    if not papers:
        logger.error("没有收集到周论文数据")
        sys.exit(1)

    logger.info(f"已收集 {len(papers)} 篇周论文")

    # 生成论文
    generator = PaperGeneratorAgent()
    paper = generator.generate_monthly(papers)

    # 保存
    filepath = save_paper(paper, output_dir, year, month)

    logger.info(f"\n=== 月论文生成完成 ===")
    logger.info(f"月份: {year} 年 {month} 月")
    logger.info(f"保存位置: {filepath}")


if __name__ == "__main__":
    main()
