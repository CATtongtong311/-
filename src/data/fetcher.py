"""统一数据获取接口，对外屏蔽多源差异。"""

from dataclasses import dataclass, field

from loguru import logger

from src.data.akshare_adapter import AkshareAdapter
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
    """统一数据获取器：优先 Tushare，失败自动降级 AKShare。"""

    def __init__(self, tushare_token: str):
        self.quota = QuotaManager()
        self.validator = DataValidator()
        self.tushare = TushareAdapter(token=tushare_token, quota=self.quota)
        self.akshare = AkshareAdapter()

    def get_stock_quote(self, symbol: str) -> StockQuote:
        """获取个股行情，自动降级。"""
        warnings: list[str] = []

        # 优先 Tushare
        data = self.tushare.get_daily_quote(symbol)
        if data:
            result = self.validator.validate_quote(data)
            warnings.extend(result.warnings)
            if result.is_valid and not result.fallback_needed:
                return self._build_stock_quote(symbol, data, warnings)

        # 触发降级：Tushare 失败、数据异常或额度不足
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
                return self._build_stock_quote(symbol, data, warnings)
            warnings.extend(result.warnings)

        # 双源均失败
        logger.error("无法获取 {} 的行情数据", symbol)
        warnings.append("数据暂不可用")
        return StockQuote(symbol=symbol, name="", source="failed", warnings=warnings)

    def get_global_market(self) -> MarketSnapshot:
        """获取全球市场数据，自动降级。"""
        warnings: list[str] = []

        data = self.tushare.get_global_market()
        result = self.validator.validate_market_data(data)
        if result.is_valid and not result.fallback_needed:
            return self._build_market_snapshot(data, warnings)

        logger.info("降级到 AKShare 获取全球市场数据")
        data = self.akshare.get_global_market()
        result = self.validator.validate_market_data(data)
        warnings.extend(result.warnings)
        if result.is_valid:
            return self._build_market_snapshot(data, warnings)

        warnings.append("全球市场数据暂不可用")
        return MarketSnapshot(source="failed", warnings=warnings)

    def get_news(self, symbol: str) -> list[dict]:
        """获取个股新闻，自动降级。"""
        news = self.tushare.get_news(symbol)
        if news:
            return news

        logger.info("降级到 AKShare 获取新闻")
        return self.akshare.get_news(symbol)

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
