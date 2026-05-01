"""
跨天去重缓存管理
管理 seen_items.json，记录已收录的 URL/DOI/标题签名

格式:
{
    "urls": {"url": "first_seen_date"},
    "dois": {"doi": "first_seen_date"},
    "title_hashes": {"hash": "first_seen_date"},
    "last_updated": "YYYY-MM-DD"
}
"""

import json
import os
import hashlib
import re
import logging
from datetime import datetime, timedelta
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)


class DedupCache:
    """跨天去重缓存"""

    def __init__(self, max_age_days: int = 90):
        self.urls: dict[str, str] = {}
        self.dois: dict[str, str] = {}
        self.title_hashes: dict[str, str] = {}
        self.last_updated: str = ""
        self.max_age_days = max_age_days

    def load(self, path: str) -> bool:
        """从 JSON 文件加载缓存"""
        if not os.path.exists(path):
            logger.info(f"  [去重缓存] 缓存文件不存在，将创建新缓存: {path}")
            return False
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.urls = data.get("urls", {})
            self.dois = data.get("dois", {})
            self.title_hashes = data.get("title_hashes", {})
            self.last_updated = data.get("last_updated", "")
            self._prune()
            logger.info(f"  [去重缓存] 已加载: {len(self.urls)} URLs, "
                        f"{len(self.dois)} DOIs, {len(self.title_hashes)} title hashes")
            return True
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"  [去重缓存] 加载失败: {e}, 使用空缓存")
            return False

    def save(self, path: str):
        """保存缓存到 JSON 文件"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._prune()
        self.last_updated = datetime.now().strftime("%Y-%m-%d")
        data = {
            "urls": self.urls,
            "dois": self.dois,
            "title_hashes": self.title_hashes,
            "last_updated": self.last_updated
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"  [去重缓存] 已保存: {len(self.urls)} URLs, "
                    f"{len(self.dois)} DOIs, {len(self.title_hashes)} title hashes")

    def is_seen_url(self, url: str) -> bool:
        """检查 URL 是否已收录（归一化后比较）"""
        return self._normalize_url(url) in self.urls

    def is_seen_doi(self, doi: str) -> bool:
        """检查 DOI 是否已收录"""
        return doi.strip().lower() in self.dois

    def is_seen_title(self, title: str) -> bool:
        """检查标题（规范化哈希）是否已收录"""
        if not title:
            return False
        h = self._hash_title(title)
        return h in self.title_hashes

    def mark_seen(self, item: dict) -> int:
        """标记一条内容为已收录（URL 归一化后存储）。返回新增标记数（0-3）"""
        today = datetime.now().strftime("%Y-%m-%d")
        count = 0
        raw_url = (item.get("url") or "").strip()
        url = self._normalize_url(raw_url) if raw_url else ""
        doi = (item.get("doi") or "").strip().lower()
        title = (item.get("title") or "").strip()

        if url and url not in self.urls:
            self.urls[url] = today
            count += 1
        if doi and doi not in self.dois:
            self.dois[doi] = today
            count += 1
        if title:
            h = self._hash_title(title)
            if h not in self.title_hashes:
                self.title_hashes[h] = today
                count += 1
        return count

    def mark_batch_seen(self, items: list[dict]):
        """批量标记"""
        total = 0
        for item in items:
            total += self.mark_seen(item)
        logger.info(f"  [去重缓存] 新增 {total} 条标记")

    def filter_seen(self, items: list[dict]) -> tuple[list[dict], list[dict]]:
        """过滤已收录的条目（URL 归一化后比较），返回 (未收录条目, 已收录条目)"""
        fresh = []
        seen = []
        for item in items:
            raw_url = (item.get("url") or "").strip()
            url = self._normalize_url(raw_url) if raw_url else ""
            doi = (item.get("doi") or "").strip().lower()
            title = (item.get("title") or "").strip()

            if (url and url in self.urls) or \
               (doi and doi in self.dois) or \
               (title and self._hash_title(title) in self.title_hashes):
                seen.append(item)
            else:
                fresh.append(item)
        if seen:
            logger.info(f"  [去重缓存] 跨天过滤 {len(seen)} 条重复内容")
        return fresh, seen

    # 追踪/营销参数黑名单
    _TRACKING_PARAMS = {
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_term',
        'utm_content', 'utm_id', 'fbclid', 'gclid', 'gclsrc',
        'ref', 'source', 'mc_cid', 'mc_eid', 'pk_campaign',
        'pk_source', 'pk_medium', 'igshid', 'twclid',
        'at_campaign', 'at_medium', 's_kwcid', 'yclid',
        'oly_anon_id', 'oly_enc_id', '_ga', '_gl',
        'trk', 'campaign_id', 'hss_channel', 'utm_custom',
    }

    @staticmethod
    def _normalize_url(url: str) -> str:
        """URL 归一化：去追踪参数、去尾部斜杠、去 www、统一协议和大小写"""
        if not url:
            return ""
        url = url.strip().lower()
        try:
            parsed = urlparse(url)
        except Exception:
            return url
        # 统一 http→https
        scheme = 'https' if parsed.scheme in ('http', 'https') else parsed.scheme
        # 移除 www 前缀
        netloc = parsed.netloc
        if netloc.startswith('www.'):
            netloc = netloc[4:]
        # 移除追踪参数
        if parsed.query:
            qs_pairs = parsed.query.split('&')
            clean = [p for p in qs_pairs
                     if '=' in p and p.split('=', 1)[0].lower() not in DedupCache._TRACKING_PARAMS]
            query = '&'.join(sorted(clean)) if clean else ''
        else:
            query = ''
        # 去尾部斜杠
        path = parsed.path.rstrip('/')
        normalized = urlunparse((scheme, netloc, path, parsed.params, query, ''))
        return normalized

    @staticmethod
    def _hash_title(title: str) -> str:
        """规范化标题并生成哈希"""
        normalized = title.lower().strip()
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]

    def _prune(self):
        """删除超过 max_age_days 天的条目"""
        cutoff = (datetime.now() - timedelta(days=self.max_age_days)).strftime("%Y-%m-%d")
        before = len(self.urls) + len(self.dois) + len(self.title_hashes)
        self.urls = {k: v for k, v in self.urls.items() if v >= cutoff}
        self.dois = {k: v for k, v in self.dois.items() if v >= cutoff}
        self.title_hashes = {k: v for k, v in self.title_hashes.items() if v >= cutoff}
        after = len(self.urls) + len(self.dois) + len(self.title_hashes)
        removed = before - after
        if removed > 0:
            logger.info(f"  [去重缓存] 清理 {removed} 条过期条目（>{self.max_age_days}天）")
