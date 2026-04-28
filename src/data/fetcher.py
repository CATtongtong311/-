"""统一数据获取接口，对外屏蔽多源差异，支持本地缓存优先策略。"""

from dataclasses import dataclass, field

from loguru import logger

from src.data.akshare_adapter import AkshareAdapter
from src.data.itick_adapter import ItickAdapter
from src.data.local_cache import LocalCache
from src.data.quota import QuotaManager
from src.data.tushare_adapter import TushareAdapter
from src.data.validator import DataValidator


@dataclass
class StockQuote:
    """个股行情数据。"""

    symbol: str
    name: str = ""
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None
    turnover: float | None = None
    change_pct: float | None = None
    source: str = ""
    trade_date: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class MarketSnapshot:
    """全球市场快照。"""

    dow_jones: dict | None = None
    sp500: dict | None = None
    nasdaq: dict | None = None
    hsi_futures: dict | None = None
    usdx: dict | None = None
    usdcnh: dict | None = None
    us_10y: dict | None = None
    source: str = ""
    warnings: list[str] = field(default_factory=list)


class DataFetcher:
    """统一数据获取器：本地缓存优先，无缓存时自动降级 Tushare → AKShare → iTick。"""

    def __init__(self, tushare_token: str):
        self.cache = LocalCache(ttl_hours=24)
        self.quota = QuotaManager()
        self.validator = DataValidator()
        self.tushare = TushareAdapter(token=tushare_token, quota=self.quota)
        self.akshare = AkshareAdapter()
        self.itick = ItickAdapter()

    def get_stock_quote(self, symbol: str, force_refresh: bool = False) -> StockQuote:
        """获取个股行情，优先本地缓存，自动降级多源 API。"""
        warnings: list[str] = []

        # 1. 本地缓存优先（除非强制刷新）
        if not force_refresh:
            cached = self.cache.get_quote(symbol)
            if cached:
                logger.debug("命中本地缓存行情: {}", symbol)
                return self._build_stock_quote(symbol, cached, warnings)

        # 2. Tushare
        data = self.tushare.get_daily_quote(symbol)
        if data:
            result = self.validator.validate_quote(data)
            warnings.extend(result.warnings)
            if result.is_valid and not result.fallback_needed:
                self.cache.save_quote(symbol, data)
                return self._build_stock_quote(symbol, data, warnings)

        # 3. 降级 AKShare
        if not data:
            logger.info("Tushare 未返回数据，降级到 AKShare")
        elif self.quota.should_fallback():
            logger.info("Tushare 额度预警，降级到 AKShare")
        else:
            logger.info("Tushare 数据校验异常，降级到 AKShare")

        data = self.akshare.get_daily_quote(symbol)
        if data:
            result = self.validator.validate_quote(data)
            warnings.extend(result.warnings)
            if result.is_valid:
                self.cache.save_quote(symbol, data)
                return self._build_stock_quote(symbol, data, warnings)
            warnings.extend(result.warnings)

        # 4. 再降级 iTick
        logger.info("AKShare 未返回有效数据，降级到 iTick")
        data = self.itick.get_daily_quote(symbol)
        if data:
            result = self.validator.validate_quote(data)
            warnings.extend(result.warnings)
            if result.is_valid:
                self.cache.save_quote(symbol, data)
                return self._build_stock_quote(symbol, data, warnings)
            warnings.extend(result.warnings)

        # 5. 全部失败
        logger.error("无法获取 {} 的行情数据", symbol)
        warnings.append("数据暂不可用")
        return StockQuote(symbol=symbol, name="", source="failed", warnings=warnings)

    def get_global_market(self, force_refresh: bool = False) -> MarketSnapshot:
        """获取全球市场数据，优先本地缓存。"""
        warnings: list[str] = []

        # 1. 本地缓存优先
        if not force_refresh:
            cached = self.cache.get_market()
            if cached:
                logger.debug("命中本地缓存全球市场数据")
                return self._build_market_snapshot(cached, warnings)

        # 2. Tushare
        data = self.tushare.get_global_market()
        result = self.validator.validate_market_data(data)
        if result.is_valid and not result.fallback_needed:
            self.cache.save_market(data)
            return self._build_market_snapshot(data, warnings)

        # 3. 降级 AKShare
        logger.info("降级到 AKShare 获取全球市场数据")
        data = self.akshare.get_global_market()
        result = self.validator.validate_market_data(data)
        warnings.extend(result.warnings)
        if result.is_valid:
            self.cache.save_market(data)
            return self._build_market_snapshot(data, warnings)

        # 4. 再降级 iTick
        logger.info("降级到 iTick 获取全球市场数据")
        data = self.itick.get_global_market()
        result = self.validator.validate_market_data(data)
        warnings.extend(result.warnings)
        if result.is_valid:
            self.cache.save_market(data)
            return self._build_market_snapshot(data, warnings)

        warnings.append("全球市场数据暂不可用")
        return MarketSnapshot(source="failed", warnings=warnings)

    def get_news(self, symbol: str, force_refresh: bool = False) -> list[dict]:
        """获取个股新闻，优先本地缓存。"""
        # 1. 本地缓存优先
        if not force_refresh:
            cached = self.cache.get_news(symbol)
            if cached is not None:
                logger.debug("命中本地缓存新闻: {}", symbol)
                return cached

        # 2. Tushare
        news = self.tushare.get_news(symbol)
        if news:
            self.cache.save_news(symbol, news)
            return news

        # 3. 降级 AKShare
        logger.info("降级到 AKShare 获取新闻")
        news = self.akshare.get_news(symbol)
        if news:
            self.cache.save_news(symbol, news)
            return news

        return []

    def _build_stock_quote(self, symbol: str, data: dict, warnings: list[str]) -> StockQuote:
        """从标准化 dict 组装 StockQuote。"""
        return StockQuote(
            symbol=symbol,
            name=data.get("name", ""),
            open=data.get("open"),
            high=data.get("high"),
            low=data.get("low"),
            close=data.get("close"),
            volume=data.get("volume"),
            turnover=data.get("turnover"),
            change_pct=data.get("change_pct"),
            source=data.get("source", ""),
            trade_date=data.get("trade_date", ""),
            warnings=warnings,
        )

    def _build_market_snapshot(self, data: dict, warnings: list[str]) -> MarketSnapshot:
        """从标准化 dict 组装 MarketSnapshot。"""
        return MarketSnapshot(
            dow_jones=data.get("dow_jones"),
            sp500=data.get("sp500"),
            nasdaq=data.get("nasdaq"),
            hsi_futures=data.get("hsi_futures"),
            usdx=data.get("usdx"),
            usdcnh=data.get("usdcnh"),
            us_10y=data.get("us_10y"),
            source=data.get("source", ""),
            warnings=warnings,
        )
