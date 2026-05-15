"""
OpenCLI Runner — 统一封装 OpenCLI 子进程调用
支持万方、百度学术、小红书等数据源。Mac/Win 双平台兼容。
"""

import subprocess
import json
import logging
import re
import shutil
import platform
from typing import Optional

logger = logging.getLogger(__name__)

IS_WINDOWS = platform.system() == "Windows"


class OpenCLIRunner:
    """OpenCLI 命令封装，通过 subprocess 调用 opencli"""

    def __init__(self, opencli_path: str = None, timeout: int = 90):
        self.path = opencli_path or self._find_opencli()
        self.timeout = timeout
        self._available: Optional[bool] = None
        self._daemon_restarted = False

    @staticmethod
    def _find_opencli() -> str:
        """动态检测 opencli 路径"""
        # 优先用 shutil.which，Windows 上用 where
        found = shutil.which("opencli")
        if found:
            return found
        return "opencli"  # fallback

    def _run_cmd(self, args: list[str]) -> subprocess.CompletedProcess:
        """跨平台 subprocess 调用"""
        kwargs = {
            "capture_output": True,
            "text": True,
            "timeout": self.timeout,
            "encoding": "utf-8",
        }
        if IS_WINDOWS:
            kwargs["shell"] = True
            # Windows 需要用字符串拼接命令，统一加 self.path 前缀
            cmd = " ".join(f'"{a}"' if " " in a else a for a in ([self.path] + args))
            return subprocess.run(cmd, **kwargs)
        else:
            return subprocess.run([self.path] + args, **kwargs)

    def _restart_daemon(self) -> bool:
        """尝试重启 OpenCLI daemon"""
        if self._daemon_restarted:
            return False
        self._daemon_restarted = True
        try:
            self._run_cmd(["daemon", "restart"])
            logger.info("  [OpenCLI] daemon 已重启")
            return True
        except Exception as e:
            logger.warning(f"  [OpenCLI] daemon 重启失败: {e}")
            return False

    def is_available(self) -> bool:
        """检查 OpenCLI 是否可用（daemon + 扩展），自动尝试启动 Chrome"""
        if self._available is not None:
            return self._available

        try:
            result = self._run_cmd(["doctor"])
            if "Extension: connected" in result.stdout and result.returncode == 0:
                self._available = True
                logger.info("  [OpenCLI] 可用 (扩展已连接)")
            else:
                # 尝试重启 daemon
                if self._restart_daemon():
                    import time
                    time.sleep(3)
                    result2 = self._run_cmd(["doctor"])
                    if "Extension: connected" in result2.stdout and result2.returncode == 0:
                        self._available = True
                        logger.info("  [OpenCLI] daemon 重启后可用")
                    else:
                        # 尝试启动 Chrome
                        if self._launch_chrome():
                            time.sleep(5)
                            result3 = self._run_cmd(["doctor"])
                            if "Extension: connected" in result3.stdout and result3.returncode == 0:
                                self._available = True
                                logger.info("  [OpenCLI] Chrome 启动后可用")
                            else:
                                self._available = False
                                logger.warning("  [OpenCLI] Chrome 已启动但扩展未连接")
                        else:
                            self._available = False
                            logger.warning("  [OpenCLI] 扩展未连接且无法启动 Chrome")
                else:
                    # 直接尝试启动 Chrome
                    if self._launch_chrome():
                        import time
                        time.sleep(5)
                        result3 = self._run_cmd(["doctor"])
                        if "Extension: connected" in result3.stdout:
                            self._available = True
                            logger.info("  [OpenCLI] Chrome 启动后可用")
                        else:
                            self._available = False
                            logger.warning("  [OpenCLI] Chrome 已启动但扩展未连接")
                    else:
                        self._available = False
                        logger.warning("  [OpenCLI] 扩展未连接或不可用")
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
            self._available = False
            logger.warning(f"  [OpenCLI] 不可用: {e}")

        return self._available

    @staticmethod
    def _launch_chrome() -> bool:
        """尝试启动 Chrome 浏览器"""
        import platform
        try:
            if platform.system() == "Windows":
                subprocess.Popen([
                    "start", "chrome",
                    "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                    '--profile-directory="Default"'
                ], shell=True)
            else:
                subprocess.Popen([
                    "open", "-a", "Google Chrome",
                    "--args", "--profile-directory=Default"
                ])
            logger.info("  [OpenCLI] 已尝试启动 Chrome")
            return True
        except Exception as e:
            logger.warning(f"  [OpenCLI] 启动 Chrome 失败: {e}")
            return False

    def search_wanfang(self, query: str, max_results: int = 5) -> list[dict]:
        """万方学术搜索（公开访问）"""
        return self._search("wanfang", query, max_results, source="万方")

    def search_baidu_scholar(self, query: str, max_results: int = 5) -> list[dict]:
        """百度学术搜索（公开访问）"""
        return self._search("baidu-scholar", query, max_results, source="百度学术")

    def search_xiaohongshu(self, query: str, max_results: int = 5) -> list[dict]:
        """小红书关键词搜索（需登录）"""
        return self._search("xiaohongshu", query, max_results, source="小红书")

    # ---- 内部方法 ----

    def _search(self, adapter: str, query: str, max_results: int, source: str) -> list[dict]:
        """通用搜索方法"""
        if not self.is_available():
            return []

        try:
            result = self._run_cmd([
                adapter, "search", query,
                "--limit", str(max_results), "-f", "json"
            ])
            if result.returncode != 0:
                logger.warning(f"  [{source}] 命令失败: {result.stderr[:100]}")
                return []

            items = self._parse_json_output(result.stdout, source)
            logger.info(f"    [{source}] '{query}': {len(items)} 条")
            return items

        except subprocess.TimeoutExpired:
            logger.warning(f"  [{source}] 超时: '{query}'")
        except OSError as e:
            logger.warning(f"  [{source}] 系统错误: {e}")
        return []

    @staticmethod
    def _parse_json_output(stdout: str, source: str) -> list[dict]:
        """解析 OpenCLI JSON 输出并映射到标准字段"""
        try:
            raw = json.loads(stdout)
        except json.JSONDecodeError:
            return []

        if not isinstance(raw, list):
            return []

        items = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue

            title = (entry.get("title") or "").strip()
            if not title or len(title) < 3:
                continue

            authors = (entry.get("authors") or entry.get("author") or "").strip()
            url = (entry.get("url") or "").strip()

            # Fix Wanfang URL format: OpenCLI returns periodical_/thesis_/conference_
            # with underscores, but Wanfang requires forward slashes
            if "wanfangdata.com.cn" in url:
                url = re.sub(r'/(periodical|thesis|conference)_', r'/\1/', url)

            # 学术来源 → paper 格式
            if source in ("万方", "百度学术", "知网"):
                journal = (entry.get("journal") or entry.get("source") or "").strip()
                year = (entry.get("year") or entry.get("date") or "").strip()
                item = {
                    "title": title,
                    "authors": authors,
                    "abstract": entry.get("abstract", ""),
                    "url": url,
                    "doi": entry.get("doi", ""),
                    "venue": journal,
                    "published_date": year,
                    "category": "chinese-academic",
                    "source": source,
                    "cited": entry.get("cited", ""),
                }
            # 小红书 → news 格式
            else:
                likes = entry.get("likes", "")
                published_at = entry.get("published_at", "")
                author_name = entry.get("author", "")
                item = {
                    "title": title,
                    "summary": "",
                    "source": f"小红书 ({author_name})" if author_name else "小红书",
                    "url": url,
                    "date": published_at[:10] if published_at else "",
                    "category": "social-media",
                    "likes": likes,
                    "author": author_name,
                }

            items.append(item)

        return items
