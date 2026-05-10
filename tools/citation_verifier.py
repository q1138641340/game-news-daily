"""
Citation Verification Layer — 真实验证参考文献
支持 DOI (Crossref), URL (HTTP), arXiv ID 三种验证方式
"""
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)

SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'ResearchVerifier/1.0 (mailto:research@example.com)'
})
SESSION.timeout = 10


def check_doi(doi: str) -> Optional[dict]:
    """
    通过 Crossref API 验证 DOI 是否存在。

    Returns:
        None if invalid/unreachable, else {title, authors, venue, year, type}
    """
    if not doi or not doi.startswith("10."):
        return None

    # 清理 DOI（去 URL 前缀）
    doi = doi.strip().replace("https://doi.org/", "")

    try:
        url = f"https://api.crossref.org/works/{doi}"
        resp = SESSION.get(url, timeout=10)
        if resp.status_code != 200:
            logger.debug(f"[DOI check] {doi}: HTTP {resp.status_code}")
            return None

        data = resp.json()
        msg = data.get("message", {})

        title_list = msg.get("title", [])
        title = title_list[0] if title_list else ""

        authors = ", ".join(
            f"{a.get('given', '')} {a.get('family', '')}".strip()
            for a in msg.get("author", [])[:5]
        )

        venue_list = msg.get("container-title", [])
        venue = venue_list[0] if venue_list else ""

        year = msg.get("created", {}).get("date-parts", [[None]])[0][0] or ""

        return {
            "title": title,
            "authors": authors,
            "venue": venue,
            "year": str(year),
            "type": msg.get("type", "unknown"),
        }

    except requests.Timeout:
        logger.debug(f"[DOI check] {doi}: timeout")
        return None
    except Exception as e:
        logger.debug(f"[DOI check] {doi}: {e}")
        return None


def check_url(url: str) -> bool:
    """HTTP HEAD 检查 URL 是否可访问（301/302/200 都算通过）"""
    if not url or not url.startswith("http"):
        return False

    try:
        resp = SESSION.head(url, timeout=8, allow_redirects=True)
        return resp.status_code in (200, 301, 302, 303, 307, 308)
    except Exception:
        return False


def check_arxiv(arxiv_id: str) -> Optional[dict]:
    """通过 arXiv API 验证论文 ID"""
    if not arxiv_id:
        return None

    # 清理 ID，去除 "arxiv:" 前缀和版本号
    arxiv_id = arxiv_id.strip().replace("arxiv:", "").split("v")[0]
    if not arxiv_id:
        return None

    try:
        url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}&max_results=1"
        resp = SESSION.get(url, timeout=12)
        if resp.status_code != 200:
            return None

        text = resp.text
        # 简单检查返回是否包含有效条目
        if "<entry>" not in text or "<title>" not in text:
            return None

        import re
        title_match = re.search(r'<title>(.*?)</title>', text, re.DOTALL)
        title = title_match.group(1).strip() if title_match else ""

        return {
            "title": title,
            "arxiv_id": arxiv_id,
            "type": "journal-article",
        }

    except Exception as e:
        logger.debug(f"[arXiv check] {arxiv_id}: {e}")
        return None


def verify_citation(ref_dict: dict) -> dict:
    """
    综合验证一条引用。

    Args:
        ref_dict: 包含 at least one of: doi, url, arxiv_id

    Returns:
        {"valid": bool, "confidence": float, "verified_by": str, "metadata": dict|None, "reason": str}
    """
    doi = ref_dict.get("doi", "")
    url = ref_dict.get("url", "")
    title = ref_dict.get("title", "")
    arxiv_id = None

    # 尝试从 URL 或 DOI 提取 arXiv ID
    if "arxiv" in str(url).lower() or "arxiv" in str(doi).lower():
        import re
        match = re.search(r'arxiv[^:]*(?::|/)(\d+\.\d+)', f"{url} {doi}")
        if match:
            arxiv_id = match.group(1)

    verified_by = None
    metadata = None
    confidence = 0.0
    valid = False
    reason = ""

    # 1. DOI 验证（最高权重）
    if doi:
        meta = check_doi(doi)
        if meta:
            confidence = 0.95
            valid = True
            verified_by = f"Crossref DOI: {doi}"
            metadata = meta
            reason = "DOI verified via Crossref API"
            # 标题一致性加分
            if title and meta["title"]:
                title_words = set(title.lower().split())
                meta_words = set(meta["title"].lower().split())
                overlap = len(title_words & meta_words) / max(len(title_words | meta_words), 1)
                if overlap > 0.3:
                    confidence = min(1.0, confidence + 0.05)
                else:
                    confidence = 0.5  # DOI 存在但标题不匹配，可疑
                    reason += " (title mismatch)"
        else:
            confidence = 0.1
            reason = "DOI not found in Crossref"

    # 2. arXiv 验证
    elif arxiv_id:
        meta = check_arxiv(arxiv_id)
        if meta:
            confidence = 0.90
            valid = True
            verified_by = f"arXiv ID: {arxiv_id}"
            metadata = meta
            reason = "arXiv ID verified"

    # 3. URL 验证（最低权重，仅做可达性检查）
    elif url:
        if check_url(url):
            confidence = 0.4
            reason = "URL is reachable"
        else:
            confidence = 0.1
            reason = "URL unreachable"

    else:
        confidence = 0.0
        reason = "No verifiable identifier (DOI/URL/arXiv)"

    return {
        "valid": valid,
        "confidence": min(confidence, 1.0),
        "verified_by": verified_by or "none",
        "metadata": metadata,
        "reason": reason,
    }


def verify_batch(refs: list[dict]) -> list[dict]:
    """
    批量验证引用列表，为每条引用添加验证结果。

    Returns:
        带有 verified, confidence_score, verification_detail 字段的引用列表
    """
    results = []
    verified_count = 0

    for i, ref in enumerate(refs):
        result = verify_citation(ref)
        ref["verified"] = result["valid"]
        ref["confidence_score"] = result["confidence"]
        ref["verification_detail"] = result["reason"]

        if result["valid"]:
            verified_count += 1
            # 用 API 返回的元数据补充缺失字段
            if result["metadata"]:
                meta = result["metadata"]
                if not ref.get("title") and meta.get("title"):
                    ref["title"] = meta["title"]
                if not ref.get("authors") and meta.get("authors"):
                    ref["authors"] = meta["authors"]
                if not ref.get("venue") and meta.get("venue"):
                    ref["venue"] = meta.get("venue")

        results.append(ref)

    total = len(refs)
    logger.info(f"  [引用验证] {verified_count}/{total} 条通过 ({(verified_count/total*100):.0f}%)")

    return results
