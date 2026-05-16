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
        self.title_keywords: dict[str, str] = {}  # 新增：标题关键词序列模糊去重
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
            self.title_keywords = data.get("title_keywords", {})  # 加载新增字段
            self.last_updated = data.get("last_updated", "")
            self._prune()
            logger.info(f"  [去重缓存] 已加载: {len(self.urls)} URLs, "
                        f"{len(self.dois)} DOIs, {len(self.title_hashes)} title hashes, "
                        f"{len(self.title_keywords)} title keywords")
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
            "title_keywords": self.title_keywords,
            "last_updated": self.last_updated
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"  [去重缓存] 已保存: {len(self.urls)} URLs, "
                    f"{len(self.dois)} DOIs, {len(self.title_hashes)} title hashes, "
                    f"{len(self.title_keywords)} title keywords")

    def is_seen_url(self, url: str) -> bool:
        """检查 URL 是否已收录（归一化后比较）"""
        return self._normalize_url(url) in self.urls

    def is_seen_doi(self, doi: str) -> bool:
        """检查 DOI 是否已收录"""
        return doi.strip().lower() in self.dois

    def is_seen_title(self, title: str) -> bool:
        """检查标题（规范化哈希或关键词重叠度）是否已收录"""
        if not title:
            return False
        # 精确哈希检查
        h = self._hash_title(title)
        if h in self.title_hashes:
            return True
        # 关键词重叠检查：与已有标题共享 >=50% 的词 → 认为重复
        new_kw = set(self._title_to_key_words(title).split('|'))
        if not new_kw:
            return False
        for existing_kw_str in self.title_keywords:
            existing_kw = set(existing_kw_str.split('|'))
            overlap = len(new_kw & existing_kw)
            # 新标题与已有标题共享 >=2 个词，或重叠率 >=50%
            if overlap >= 2 or (overlap >= 1 and overlap / len(new_kw) >= 0.5):
                return True
        return False

    def mark_seen(self, item: dict) -> int:
        """标记一条内容为已收录（URL 归一化后存储）。返回新增标记数（0-4）"""
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
            # 同时存储关键词序列（用于模糊去重）
            kw = self._title_to_key_words(title)
            if kw and kw not in self.title_keywords:
                self.title_keywords[kw] = today
                count += 1
        return count

    def mark_batch_seen(self, items: list[dict]):
        """批量标记"""
        total = 0
        for item in items:
            total += self.mark_seen(item)
        logger.info(f"  [去重缓存] 新增 {total} 条标记")

    def filter_seen(self, items: list[dict]) -> tuple[list[dict], list[dict]]:
        """过滤已收录的条目（URL/DOI/精确哈希/关键词重叠），返回 (未收录条目, 已收录条目)"""
        fresh = []
        seen = []
        for item in items:
            raw_url = (item.get("url") or "").strip()
            url = self._normalize_url(raw_url) if raw_url else ""
            doi = (item.get("doi") or "").strip().lower()
            title = (item.get("title") or "").strip()

            # 检查所有去重维度
            url_match = url and url in self.urls
            doi_match = doi and doi in self.dois
            hash_match = title and self._hash_title(title) in self.title_hashes
            kw_match = False
            if title:
                new_kw = set(self._title_to_key_words(title).split('|'))
                if new_kw:
                    for existing_kw_str in self.title_keywords:
                        existing_kw = set(existing_kw_str.split('|'))
                        overlap = len(new_kw & existing_kw)
                        if overlap >= 2 or (overlap >= 1 and overlap / len(new_kw) >= 0.5):
                            kw_match = True
                            break

            if url_match or doi_match or hash_match or kw_match:
                seen.append(item)
            else:
                fresh.append(item)
        if seen:
            url_dup = sum(1 for i in items if self._normalize_url((i.get("url") or "").strip()) in self.urls)
            doi_dup = sum(1 for i in items if (i.get("doi") or "").strip().lower() in self.dois)
            hash_dup = sum(1 for i in items if self._hash_title((i.get("title") or "").strip()) in self.title_hashes)
            kw_dup = len(seen) - url_dup - doi_dup - hash_dup
            logger.info(f"  [去重缓存] 跨天过滤 {len(seen)} 条重复内容（URL:{url_dup} DOI:{doi_dup} 哈希:{hash_dup} 关键词重叠:{kw_dup})")
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
        # 统一 twitter.com 和 x.com（两者指向同一平台）
        if netloc in ('twitter.com', 'x.com'):
            netloc = 'twitter.com'
        # 处理 xhslink.com 等短链接（保留原样，不做归一化，避免误匹配）
        # 小红书短链接需要完整 fetch 才能拿到真实 URL，超出缓存层职责
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
        # 移除所有标点符号（包括中文破折号、顿号等），但保留中文和英文文字
        normalized = re.sub(r'[^\w\s]', '', normalized, flags=re.UNICODE)
        # 统一全角数字为半角
        normalized = re.sub(r'[０-９]', lambda m: chr(ord(m.group()) - 0xFEE0), normalized)
        # 统一全角字母为半角
        normalized = re.sub(r'[Ａ-Ｚａ-ｚ]', lambda m: chr(ord(m.group()) - 0xFEE0), normalized)
        # 压缩所有空白字符为单个空格
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]

    @staticmethod
    def _title_to_key_words(title: str) -> str:
        """提取标题关键词序列（用于模糊匹配）"""
        normalized = title.lower().strip()
        normalized = re.sub(r'[^\w\s]', '', normalized, flags=re.UNICODE)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        # 提取长度>=2的中文词（每3个字为一个词）和英文单词
        words = []
        # 中文：每3字切分
        i = 0
        while i < len(normalized):
            if normalized[i].isascii():
                # 英文字符，提取单词
                j = i
                while j < len(normalized) and not normalized[j].isspace() and normalized[j] not in '，。！？；：""''（）':
                    j += 1
                word = normalized[i:j]
                if len(word) >= 3:
                    words.append(word)
                i = j + 1
            else:
                # 中文字符，提取3字词
                word = normalized[i:i+3]
                if len(word) >= 3:
                    words.append(word)
                i += 3
        return '|'.join(sorted(words))

    def _prune(self):
        """删除超过 max_age_days 天的条目"""
        cutoff = (datetime.now() - timedelta(days=self.max_age_days)).strftime("%Y-%m-%d")
        before = len(self.urls) + len(self.dois) + len(self.title_hashes) + len(self.title_keywords)
        self.urls = {k: v for k, v in self.urls.items() if v >= cutoff}
        self.dois = {k: v for k, v in self.dois.items() if v >= cutoff}
        self.title_hashes = {k: v for k, v in self.title_hashes.items() if v >= cutoff}
        self.title_keywords = {k: v for k, v in self.title_keywords.items() if v >= cutoff}
        after = len(self.urls) + len(self.dois) + len(self.title_hashes) + len(self.title_keywords)
        removed = before - after
        if removed > 0:
            logger.info(f"  [去重缓存] 清理 {removed} 条过期条目（>{self.max_age_days}天）")
