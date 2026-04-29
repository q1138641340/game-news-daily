"""
Obsidian 写入工具
将内容写入 Obsidian vault 的指定文件夹
"""

import os
from datetime import datetime
from typing import Optional


class ObsidianWriter:
    """Obsidian vault 写入器"""

    def __init__(self, vault_path: str, output_folder: str = "Research Feed"):
        """
        初始化写入器

        Args:
            vault_path: Obsidian vault 的绝对路径
            output_folder: vault 内的输出文件夹名称
        """
        self.vault_path = vault_path
        self.output_folder = output_folder
        self.base_dir = os.path.join(vault_path, output_folder)
        os.makedirs(self.base_dir, exist_ok=True)

    def write_daily_report(
        self,
        content: str,
        date: Optional[str] = None,
        tags: Optional[list[str]] = None,
        failed_papers: Optional[list[dict]] = None,
        filepath: Optional[str] = None
    ) -> str:
        """
        写入日报文件

        Args:
            content: Markdown 内容（不含 frontmatter）
            date: 日期字符串 (YYYY-MM-DD)，默认今天
            tags: 标签列表
            failed_papers: 下载失败的论文列表（会追加到日报末尾）
            filepath: 自定义文件路径（优先于自动生成）

        Returns:
            写入的文件路径
        """
        if filepath:
            file_path = filepath
        else:
            date = date or datetime.now().strftime("%Y-%m-%d")
            filename = f"{date}-Daily-Report.md"
            file_path = os.path.join(self.base_dir, filename)

        # 构建 frontmatter
        frontmatter = self._build_frontmatter(
            title=f"Game Research Daily - {date or 'Daily Report'}",
            date=date or datetime.now().strftime("%Y-%m-%d"),
            tags=tags or ["daily-report", "game-research"],
            type="daily-report"
        )

        full_content = frontmatter + "\n" + content

        # 追加无法下载的论文（附 DOI）
        if failed_papers:
            full_content += self._format_failed_papers(failed_papers, date)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(full_content)

        return file_path

    def write_paper_note(
        self,
        title: str,
        content: str,
        date: Optional[str] = None,
        tags: Optional[list[str]] = None,
        doi: Optional[str] = None,
        pdf_path: Optional[str] = None
    ) -> str:
        """
        写入单篇论文笔记

        Args:
            title: 论文标题
            content: Markdown 内容
            date: 日期
            tags: 标签
            doi: DOI
            pdf_path: 本地 PDF 路径

        Returns:
            写入的文件路径
        """
        date = date or datetime.now().strftime("%Y-%m-%d")
        filename = self._safe_filename(title) + ".md"
        filepath = os.path.join(self.base_dir, "Papers", filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        # 构建额外的 frontmatter 字段
        extra = {}
        if doi:
            extra["doi"] = doi
        if pdf_path:
            # 转为 Obsidian 内部链接
            relative = os.path.relpath(pdf_path, self.vault_path)
            extra["pdf"] = relative

        frontmatter = self._build_frontmatter(
            title=title,
            date=date,
            tags=tags or ["paper", "academic"],
            type="paper",
            extra=extra
        )

        full_content = frontmatter + "\n" + content

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(full_content)

        return filepath

    @staticmethod
    def _format_failed_papers(failed_papers: list[dict], date: str) -> str:
        """格式化下载失败的论文，追加到日报末尾"""
        if not failed_papers:
            return ""

        lines = ["\n\n---\n\n## 未能下载的论文\n\n"]
        lines.append(f"以下论文无法下载 PDF，请通过 DOI 直接访问：\n\n")

        for i, paper in enumerate(failed_papers, 1):
            title = paper.get("title", "Unknown Title")
            doi = paper.get("doi", "")
            url = paper.get("url", "")
            source = paper.get("venue", paper.get("source", ""))

            lines.append(f"### {i}. {title}\n")
            if doi:
                lines.append(f"**DOI**: [{doi}](https://doi.org/{doi})\n")
            elif url:
                lines.append(f"**URL**: [{url}]({url})\n")
            if source:
                lines.append(f"**来源**: {source}\n")
            lines.append("\n")

        return "".join(lines)

    def write_failed_downloads(self, failed_papers: list[dict], date: str) -> str:
        """
        已废弃：下载失败列表现在整合进日报，不再单独生成文件
        保留此方法以避免代码报错，但不再被调用
        """
        # 不再单独写文件，统一整合进日报
        return ""

    @staticmethod
    def _build_frontmatter(
        title: str,
        date: str,
        tags: list[str],
        type: str,
        extra: Optional[dict] = None
    ) -> str:
        """构建 YAML frontmatter"""
        lines = ["---"]
        lines.append(f"title: \"{title}\"")
        lines.append(f"date: {date}")
        lines.append(f"type: {type}")
        lines.append(f"tags:")
        for tag in tags:
            lines.append(f"  - {tag}")

        if extra:
            for key, value in extra.items():
                lines.append(f"{key}: \"{value}\"")

        lines.append("---")
        return "\n".join(lines)

    @staticmethod
    def _safe_filename(title: str) -> str:
        """将标题转为安全的文件名"""
        import re
        filename = re.sub(r'[^\w\s\-\.]', '', title)
        filename = re.sub(r'\s+', '_', filename)
        return filename[:80]