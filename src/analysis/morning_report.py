"""晨报生成器：整合全球市场、持仓事件、板块前瞻。"""

from dataclasses import dataclass, field

from loguru import logger

from src.data.fetcher import DataFetcher
from src.llm.kimi_client import KimiClient
from src.llm.prompts import MORNING_REPORT_SYSTEM, build_morning_report_prompt
from src.portfolio.parser import Portfolio, PortfolioParser


@dataclass
class MorningReport:
    """晨报结果。"""

    date: str
    content: str
    source: str = "kimi"
    warnings: list[str] = field(default_factory=list)


class MorningReportGenerator:
    """晨报生成器：每日开盘前自动生成投资晨报。"""

    def __init__(
        self,
        data_fetcher: DataFetcher,
        kimi_client: KimiClient,
        portfolio_parser: PortfolioParser | None = None,
    ):
        self.data_fetcher = data_fetcher
        self.kimi = kimi_client
        self.portfolio = portfolio_parser or PortfolioParser()

    def generate(self) -> MorningReport:
        """生成完整晨报。"""
        from datetime import date

        today = date.today().strftime("%Y-%m-%d")
        logger.info("开始生成晨报: {}", today)

        # 1. 读取持仓
        portfolio = self.portfolio.parse()

        # 2. 获取全球市场数据
        market = self.data_fetcher.get_global_market()

        # 3. 获取持仓个股新闻
        holdings_news = {}
        for holding in portfolio.holdings:
            try:
                news = self.data_fetcher.get_news(holding.symbol)
                if news:
                    holdings_news[holding.symbol] = news
            except Exception as e:
                logger.warning("获取 {} 新闻失败: {}", holding.symbol, e)

        # 4. 构建 Prompt
        prompt = build_morning_report_prompt(
            portfolio={
                "holdings": [
                    {
                        "symbol": h.symbol,
                        "name": h.name,
                        "cost_price": h.cost_price,
                        "quantity": h.quantity,
                        "sector": h.sector,
                    }
                    for h in portfolio.holdings
                ],
                "watch_sectors": portfolio.watch_sectors,
            },
            market_snapshot={
                "dow_jones": market.dow_jones,
                "sp500": market.sp500,
                "nasdaq": market.nasdaq,
                "hsi_futures": market.hsi_futures,
                "usdx": market.usdx,
                "usdcnh": market.usdcnh,
                "us_10y": market.us_10y,
            },
            holdings_news=holdings_news,
        )

        # 5. 调用 LLM
        content = self.kimi.chat(
            messages=[
                {"role": "system", "content": MORNING_REPORT_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=4096,
        )

        if not content:
            logger.error("Kimi 晨报生成返回空结果")
            return MorningReport(
                date=today,
                content="晨报生成失败，请稍后重试。",
                warnings=["AI 分析服务暂不可用"],
                source="failed",
            )

        # 6. 替换日期占位符
        content = content.replace("YYYY-MM-DD", today)

        warnings = []
        if market.source == "failed":
            warnings.append("全球市场数据获取失败")

        logger.info("晨报生成完成: {}", today)
        return MorningReport(
            date=today,
            content=content,
            warnings=warnings,
        )
