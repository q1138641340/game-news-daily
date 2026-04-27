"""
PDF 下载工具
优先下载开放获取论文，付费论文尝试其他免费源，最后提供 DOI 链接
"""

import os
import re
import time
import requests
from typing import Optional
from concurrent.futures import ThreadPoolExecutor


class PDFDownloader:
    """论文 PDF 下载器"""

    def __init__(self, output_dir: str, timeout: int = 30):
        self.output_dir = output_dir
        self.timeout = timeout
        os.makedirs(output_dir, exist_ok=True)

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36'
            )
        })

    def download(self, url: str, filename: Optional[str] = None) -> Optional[str]:
        """
        下载 PDF

        Args:
            url: PDF 的直接下载链接
            filename: 保存的文件名（可选，自动生成）

        Returns:
            保存的文件路径，失败返回 None
        """
        if not filename:
            filename = self._url_to_filename(url)

        filepath = os.path.join(self.output_dir, filename)

        # 已存在则跳过
        if os.path.exists(filepath):
            return filepath

        try:
            resp = self.session.get(url, timeout=self.timeout, stream=True)
            resp.raise_for_status()

            # 验证是否是PDF
            content_type = resp.headers.get('content-type', '')
            if 'pdf' not in content_type and not url.endswith('.pdf'):
                # 可能不是PDF，尝试读取前几个字节验证
                first_bytes = next(resp.iter_content(1024), b'')
                if not first_bytes.startswith(b'%PDF'):
                    return None
                # 写入第一个chunk
                with open(filepath, 'wb') as f:
                    f.write(first_bytes)
                    for chunk in resp.iter_content(8192):
                        f.write(chunk)
                return filepath

            with open(filepath, 'wb') as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)

            # 验证文件大小（太小可能不是有效PDF）
            if os.path.getsize(filepath) < 1024:
                os.remove(filepath)
                return None

            return filepath

        except Exception as e:
            print(f"  [下载失败] {url}: {e}")
            # 清理不完整的文件
            if os.path.exists(filepath):
                os.remove(filepath)
            return None

    def download_arxiv(self, arxiv_id: str) -> Optional[str]:
        """
        下载 arXiv 论文

        Args:
            arxiv_id: arXiv ID (如 "2401.12345")

        Returns:
            保存的文件路径
        """
        # arXiv PDF 链接格式
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        filename = f"arxiv_{arxiv_id.replace('/', '_')}.pdf"
        return self.download(pdf_url, filename)

    def download_semantic_scholar(self, paper_id: str) -> Optional[str]:
        """
        通过 Semantic Scholar 下载开放获取论文

        Args:
            paper_id: Semantic Scholar Paper ID

        Returns:
            保存的文件路径
        """
        try:
            api_url = f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}"
            params = {"fields": "openAccessPdf,title"}
            resp = requests.get(api_url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            pdf_info = data.get("openAccessPdf")
            if pdf_info and pdf_info.get("url"):
                title = data.get("title", paper_id)
                filename = self._title_to_filename(title) + ".pdf"
                return self.download(pdf_info["url"], filename)

        except Exception as e:
            print(f"  [Semantic Scholar下载失败] {paper_id}: {e}")

        return None

    def try_free_sources(self, doi: str, title: str) -> Optional[str]:
        """
        尝试从免费源下载付费论文

        依次尝试：
        1. Unpaywall (合法开放获取)
        2. PubMed Central (生物医学)
        3. 直接搜索 PDF

        Args:
            doi: 论文 DOI
            title: 论文标题

        Returns:
            保存的文件路径，全部失败返回 None
        """
        filename = self._title_to_filename(title) + ".pdf"

        # 1. Unpaywall（合法的开放获取查找）
        if doi:
            try:
                unpaywall_url = f"https://api.unpaywall.org/v2/{doi}"
                params = {"email": "research@example.com"}
                resp = requests.get(unpaywall_url, params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()

                best_oa = data.get("best_oa_location")
                if best_oa and best_oa.get("url_for_pdf"):
                    result = self.download(best_oa["url_for_pdf"], filename)
                    if result:
                        print(f"  [Unpaywall成功] {title[:50]}")
                        return result
            except Exception:
                pass

        # 2. 用标题搜索 PDF
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                query = f'"{title}" filetype:pdf'
                results = list(ddgs.text(query, max_results=3))
                for r in results:
                    url = r.get("href", "")
                    if url.endswith('.pdf') or 'pdf' in url.lower():
                        result = self.download(url, filename)
                        if result:
                            print(f"  [搜索PDF成功] {title[:50]}")
                            return result
        except Exception:
            pass

        print(f"  [无法下载] {title[:50]} -> DOI: {doi}")
        return None

    def download_batch(self, papers: list[dict], max_workers: int = 3) -> dict:
        """
        批量下载论文

        Args:
            papers: [{"url": str, "doi": str, "title": str, "source": str}]
            max_workers: 并行下载数

        Returns:
            {"downloaded": [文件路径], "failed": [论信息]}
        """
        downloaded = []
        failed = []

        def _download_one(paper):
            title = paper.get("title", "unknown")
            url = paper.get("pdf_url") or paper.get("url")
            doi = paper.get("doi", "")

            # 优先直接下载
            if url and url.endswith('.pdf'):
                result = self.download(url)
                if result:
                    return ("ok", result, paper)

            # arXiv 论文
            if url and 'arxiv.org' in url:
                arxiv_id = self._extract_arxiv_id(url)
                if arxiv_id:
                    result = self.download_arxiv(arxiv_id)
                    if result:
                        return ("ok", result, paper)

            # 尝试免费源
            if doi:
                result = self.try_free_sources(doi, title)
                if result:
                    return ("ok", result, paper)

            return ("fail", None, paper)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_download_one, p) for p in papers]
            for future in futures:
                status, path, paper = future.result()
                if status == "ok":
                    downloaded.append({"path": path, "paper": paper})
                else:
                    failed.append(paper)

        return {"downloaded": downloaded, "failed": failed}

    @staticmethod
    def _url_to_filename(url: str) -> str:
        """从URL生成文件名"""
        filename = url.split('/')[-1]
        if not filename.endswith('.pdf'):
            filename += '.pdf'
        # 清理非法字符
        filename = re.sub(r'[^\w\-_.]', '_', filename)
        return filename[:100]

    @staticmethod
    def _title_to_filename(title: str) -> str:
        """从标题生成文件名"""
        # 移除特殊字符
        filename = re.sub(r'[^\w\s\-]', '', title)
        filename = re.sub(r'\s+', '_', filename)
        return filename[:80]

    @staticmethod
    def _extract_arxiv_id(url: str) -> Optional[str]:
        """从URL中提取arXiv ID"""
        match = re.search(r'(\d{4}\.\d{4,5}(?:v\d+)?)', url)
        if match:
            return match.group(1)
        match = re.search(r'abs/([\w\-\.]+)', url)
        if match:
            return match.group(1)
        return None