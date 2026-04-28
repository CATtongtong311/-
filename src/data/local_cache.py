"""本地 JSON 缓存管理器。

缓存结构：
    data/cache/
        quotes/{symbol}_{date}.json   — 个股行情
        news/{symbol}_{date}.json     — 个股新闻
        market/{date}.json            — 全球市场数据

缓存有效期默认 24 小时，可通过 ttl_hours 参数调整。
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger

from config.settings import PROJECT_ROOT


CACHE_DIR = PROJECT_ROOT / "data" / "cache"


class LocalCache:
    """本地文件缓存，以 JSON 格式持久化数据。"""

    def __init__(self, ttl_hours: int = 24):
        self.ttl_hours = ttl_hours
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """确保缓存目录存在。"""
        for sub in ("quotes", "news", "market"):
            (CACHE_DIR / sub).mkdir(parents=True, exist_ok=True)

    # ── 个股行情 ───────────────────────────────────────────

    def get_quote(self, symbol: str) -> dict | None:
        """读取缓存的个股行情，过期返回 None。"""
        path = self._quote_path(symbol)
        return self._read_if_fresh(path)

    def save_quote(self, symbol: str, data: dict) -> None:
        """保存个股行情到缓存。"""
        path = self._quote_path(symbol)
        self._write(path, data)
        logger.debug("缓存行情已保存: {} -> {}", symbol, path.name)

    def _quote_path(self, symbol: str) -> Path:
        date_str = datetime.now().strftime("%Y%m%d")
        return CACHE_DIR / "quotes" / f"{symbol}_{date_str}.json"

    # ── 个股新闻 ───────────────────────────────────────────

    def get_news(self, symbol: str) -> list[dict] | None:
        """读取缓存的个股新闻，过期返回 None。"""
        path = self._news_path(symbol)
        raw = self._read_if_fresh(path)
        return raw if isinstance(raw, list) else None

    def save_news(self, symbol: str, news: list[dict]) -> None:
        """保存个股新闻到缓存。"""
        path = self._news_path(symbol)
        self._write(path, news)
        logger.debug("缓存新闻已保存: {} -> {} 条", symbol, len(news))

    def _news_path(self, symbol: str) -> Path:
        date_str = datetime.now().strftime("%Y%m%d")
        return CACHE_DIR / "news" / f"{symbol}_{date_str}.json"

    # ── 全球市场 ───────────────────────────────────────────

    def get_market(self) -> dict | None:
        """读取缓存的全球市场数据，过期返回 None。"""
        path = self._market_path()
        return self._read_if_fresh(path)

    def save_market(self, data: dict) -> None:
        """保存全球市场数据到缓存。"""
        path = self._market_path()
        self._write(path, data)
        logger.debug("全球市场缓存已保存: {}", path.name)

    def _market_path(self) -> Path:
        date_str = datetime.now().strftime("%Y%m%d")
        return CACHE_DIR / "market" / f"{date_str}.json"

    # ── 内部读写 ───────────────────────────────────────────

    def _read_if_fresh(self, path: Path) -> dict | list | None:
        """读取文件内容，如果文件不存在或已过期则返回 None。"""
        if not path.exists():
            return None
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            if datetime.now() - mtime > timedelta(hours=self.ttl_hours):
                logger.debug("缓存已过期: {}", path.name)
                return None
            content = path.read_text(encoding="utf-8")
            return json.loads(content)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("读取缓存失败 {}: {}", path, e)
            return None

    def _write(self, path: Path, data: dict | list) -> None:
        """写入 JSON 文件。"""
        try:
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except OSError as e:
            logger.warning("写入缓存失败 {}: {}", path, e)

    # ── 批量清理 ───────────────────────────────────────────

    def clean_expired(self, keep_days: int = 7) -> int:
        """清理 keep_days 天前的过期缓存文件，返回删除数量。"""
        cutoff = datetime.now() - timedelta(days=keep_days)
        deleted = 0
        for sub in ("quotes", "news", "market"):
            for path in (CACHE_DIR / sub).glob("*"):
                if path.is_file():
                    try:
                        mtime = datetime.fromtimestamp(path.stat().st_mtime)
                        if mtime < cutoff:
                            path.unlink()
                            deleted += 1
                    except OSError as e:
                        logger.warning("删除缓存失败 {}: {}", path, e)
        if deleted:
            logger.info("清理过期缓存: {} 个文件", deleted)
        return deleted

    # ── 预拉取辅助 ─────────────────────────────────────────

    def get_all_cached_symbols(self) -> list[str]:
        """获取今日已有缓存行情的所有股票代码。"""
        symbols = set()
        for path in (CACHE_DIR / "quotes").glob("*_*.json"):
            # 文件名格式: symbol_YYYYMMDD.json
            symbol = path.stem.split("_")[0]
            if symbol:
                symbols.add(symbol)
        return sorted(symbols)

    def get_cached_quote_as_text(self, symbol: str) -> str:
        """以文本形式返回缓存的行情数据，供 Claude Code CLI 快速查询。"""
        data = self.get_quote(symbol)
        if not data:
            return f"[{symbol}] 暂无本地缓存数据"
        lines = [f"## {data.get('name', symbol)} ({symbol})"]
        for key, label in [
            ("close", "最新价"),
            ("open", "开盘价"),
            ("high", "最高价"),
            ("low", "最低价"),
            ("change_pct", "涨跌幅%"),
            ("volume", "成交量"),
            ("turnover", "成交额"),
            ("trade_date", "交易日期"),
            ("source", "数据来源"),
        ]:
            val = data.get(key)
            if val is not None and val != "":
                lines.append(f"- {label}: {val}")
        return "\n".join(lines)

    def get_cached_market_as_text(self) -> str:
        """以文本形式返回缓存的全球市场数据。"""
        data = self.get_market()
        if not data:
            return "暂无本地全球市场缓存数据"
        lines = ["## 全球市场数据"]
        for key, label in [
            ("dow_jones", "道琼斯"),
            ("sp500", "标普500"),
            ("nasdaq", "纳斯达克"),
            ("hsi_futures", "恒生期货"),
            ("usdx", "美元指数"),
            ("usdcnh", "离岸人民币"),
            ("us_10y", "10Y美债"),
        ]:
            val = data.get(key)
            if val:
                if isinstance(val, dict) and val.get("close"):
                    lines.append(f"- {label}: {val['close']}")
                else:
                    lines.append(f"- {label}: {val}")
        lines.append(f"- 数据来源: {data.get('source', 'unknown')}")
        return "\n".join(lines)
