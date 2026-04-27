"""晨报生成器：整合全球市场、持仓事件、板块前瞻。"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

from src.data.fetcher import DataFetcher
from src.llm.claude_code_client import ClaudeCodeClient
from src.llm.prompts import MORNING_REPORT_SYSTEM, build_morning_report_prompt
from src.portfolio.parser import Portfolio, PortfolioParser


@dataclass
class MorningReport:
    """晨报结果。"""

    date: str
    content: str
    source: str = "claude"
    warnings: list[str] = field(default_factory=list)
    # 模块执行状态跟踪
    module_status: dict[str, str] = field(default_factory=dict)


class MorningReportGenerator:
    """晨报生成器：每日开盘前自动生成投资晨报。"""

    def __init__(
        self,
        data_fetcher: DataFetcher,
        llm_client: ClaudeCodeClient,
        portfolio_parser: PortfolioParser | None = None,
    ):
        self.data_fetcher = data_fetcher
        self.llm = llm_client
        self.portfolio = portfolio_parser or PortfolioParser()

    def generate(self) -> MorningReport:
        """生成完整晨报，带模块状态跟踪。"""
        from datetime import date

        today = date.today().strftime("%Y-%m-%d")
        logger.info("开始生成晨报: {}", today)
        module_status: dict[str, str] = {}

        # 1. 读取持仓
        try:
            portfolio = self.portfolio.parse()
            module_status["持仓解析"] = "成功"
        except Exception as e:
            module_status["持仓解析"] = f"失败: {e}"
            logger.error("晨报生成失败: 持仓解析异常: {}", e)
            return MorningReport(
                date=today,
                content="晨报生成失败：无法读取持仓数据。",
                warnings=[f"持仓解析异常: {e}"],
                source="failed",
                module_status=module_status,
            )

        # 2. 获取全球市场数据
        market = None
        try:
            market = self.data_fetcher.get_global_market()
            if market and getattr(market, "source", "") == "failed":
                module_status["全球市场数据"] = f"失败: {'; '.join(getattr(market, 'warnings', []))}"
            else:
                module_status["全球市场数据"] = "成功"
        except Exception as e:
            module_status["全球市场数据"] = f"失败: {e}"

        # 3. 获取持仓个股新闻
        holdings_news = {}
        news_ok = 0
        news_fail = 0
        for holding in portfolio.holdings:
            try:
                news = self.data_fetcher.get_news(holding.symbol)
                if news:
                    holdings_news[holding.symbol] = news
                news_ok += 1
            except Exception as e:
                news_fail += 1
                logger.warning("获取 {} 新闻失败: {}", holding.symbol, e)
        module_status["个股新闻"] = f"成功{news_ok}只, 失败{news_fail}只"

        # 4. 将数据直接嵌入 prompt
        data_payload = {
            "date": today,
            "portfolio": {
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
            "market": {
                "dow_jones": market.dow_jones if market else None,
                "sp500": market.sp500 if market else None,
                "nasdaq": market.nasdaq if market else None,
                "hsi_futures": market.hsi_futures if market else None,
                "usdx": market.usdx if market else None,
                "usdcnh": market.usdcnh if market else None,
                "us_10y": market.us_10y if market else None,
            },
            "holdings_news": {
                sym: [{"title": n.get("title", ""), "summary": n.get("summary", "")[:150]} for n in items]
                for sym, items in holdings_news.items()
            },
        }

        file_prompt = (
            "以下是今日投资晨报所需数据（JSON格式）：\n"
            f"```json\n{json.dumps(data_payload, ensure_ascii=False, indent=2)}\n```\n\n"
            "请根据以上数据和系统指令格式生成完整晨报，直接返回 Markdown 文本。"
        )

        # 5. 调用 Claude Code（超时 300s = 5 分钟）
        content = ""
        try:
            content = self.llm.chat(
                messages=[
                    {"role": "system", "content": MORNING_REPORT_SYSTEM},
                    {"role": "user", "content": file_prompt},
                ],
                temperature=0.4,
                max_tokens=4096,
                timeout=300,
            )
            if content:
                module_status["AI分析"] = "成功"
            else:
                module_status["AI分析"] = "失败: 返回空结果"
        except Exception as e:
            module_status["AI分析"] = f"失败: {e}"

        if not content:
            logger.error("Claude Code 晨报生成返回空结果，模块状态: {}", module_status)
            return MorningReport(
                date=today,
                content="晨报生成失败，请稍后重试。",
                warnings=["AI 分析服务暂不可用"],
                source="failed",
                module_status=module_status,
            )

        # 6. 替换日期占位符
        content = content.replace("YYYY-MM-DD", today)

        warnings = []
        if market and getattr(market, "source", "") == "failed":
            warnings.append("全球市场数据获取失败")

        logger.info("晨报生成完成: {} 模块状态: {}", today, module_status)
        return MorningReport(
            date=today,
            content=content,
            warnings=warnings,
            module_status=module_status,
        )
