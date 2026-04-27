"""诊股分析：数据获取 + LLM 分析 + 结果封装。"""

import re
from dataclasses import dataclass, field

from loguru import logger

from src.data.fetcher import DataFetcher
from src.llm.kimi_client import KimiClient
from src.llm.prompts import DIAGNOSIS_SYSTEM, build_diagnosis_prompt
from src.portfolio.parser import PortfolioParser


@dataclass
class DiagnosisResult:
    """诊股结果。"""

    symbol: str
    name: str
    score: int = 0
    strategy: str = "观望型"
    summary: str = ""
    support: float | None = None
    resistance: float | None = None
    stop_loss: float | None = None
    analysis_text: str = ""
    warnings: list[str] = field(default_factory=list)
    alert_triggered: bool = False
    alert_msg: str = ""
    source: str = "kimi"


class DiagnosisAnalyzer:
    """诊股分析器：整合数据获取、持仓上下文和 LLM 分析。"""

    def __init__(
        self,
        data_fetcher: DataFetcher,
        kimi_client: KimiClient,
        portfolio_parser: PortfolioParser | None = None,
    ):
        self.data_fetcher = data_fetcher
        self.kimi = kimi_client
        self.portfolio = portfolio_parser or PortfolioParser()

    def analyze(self, symbol: str, name: str = "") -> DiagnosisResult:
        """对指定股票进行完整诊股分析。"""
        logger.info("开始诊股分析: {}", symbol)

        # 1. 获取实时行情
        quote = self.data_fetcher.get_stock_quote(symbol)
        if quote.source == "failed":
            logger.error("无法获取 {} 的行情数据", symbol)
            return DiagnosisResult(
                symbol=symbol,
                name=name,
                warnings=quote.warnings,
                source="failed",
            )

        # 2. 获取新闻
        news = self.data_fetcher.get_news(symbol)

        # 3. 获取持仓上下文
        holding = self.portfolio.get_holding(symbol)
        holding_dict = None
        if holding:
            holding_dict = {
                "cost_price": holding.cost_price,
                "quantity": holding.quantity,
                "sector": holding.sector,
                "notes": holding.notes,
            }
            name = name or holding.name

        # 4. 检查 ±5% 警示
        alert_triggered = False
        alert_msg = ""
        if quote.close is not None and holding and holding.cost_price:
            alert_triggered, alert_msg = self.portfolio.should_alert(
                symbol, quote.close
            )
            if alert_triggered:
                logger.warning("持仓警示: {}", alert_msg)

        # 5. 构建 Prompt 并调用 LLM
        prompt = build_diagnosis_prompt(
            symbol=symbol,
            name=name or symbol,
            quote={
                "open": quote.open,
                "high": quote.high,
                "low": quote.low,
                "close": quote.close,
                "volume": quote.volume,
                "change_pct": quote.change_pct,
                "turnover": quote.turnover,
            },
            news=news,
            holding=holding_dict,
        )

        analysis_text = self.kimi.chat(
            messages=[
                {"role": "system", "content": DIAGNOSIS_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=4096,
        )

        if not analysis_text:
            logger.error("Kimi 诊股分析返回空结果")
            return DiagnosisResult(
                symbol=symbol,
                name=name,
                warnings=["AI 分析服务暂不可用"],
                source="failed",
            )

        # 6. 解析结构化数据
        result = self._parse_analysis(symbol, name, analysis_text)
        result.warnings.extend(quote.warnings)
        result.alert_triggered = alert_triggered
        result.alert_msg = alert_msg
        result.analysis_text = analysis_text

        logger.info("诊股分析完成: {} 评分={} 策略={}", symbol, result.score, result.strategy)
        return result

    def _parse_analysis(self, symbol: str, name: str, text: str) -> DiagnosisResult:
        """从 LLM 输出中解析结构化字段。"""
        result = DiagnosisResult(symbol=symbol, name=name)

        # 解析评分
        score_match = re.search(r"综合评分[:：]\s*(\d+)/100", text)
        if score_match:
            result.score = int(score_match.group(1))

        # 解析策略建议
        strategy_match = re.search(r"策略建议[:：]\s*(进攻型|防御型|观望型)", text)
        if strategy_match:
            result.strategy = strategy_match.group(1)

        # 解析支撑/压力位
        support_match = re.search(r"支撑\s*[:：]?\s*(\d+\.?\d*)", text)
        if support_match:
            result.support = float(support_match.group(1))

        resistance_match = re.search(r"压力\s*[:：]?\s*(\d+\.?\d*)", text)
        if resistance_match:
            result.resistance = float(resistance_match.group(1))

        stop_match = re.search(r"止损(?:参考)?\s*[:：]?\s*(\d+\.?\d*)", text)
        if stop_match:
            result.stop_loss = float(stop_match.group(1))

        # 一句话总结
        summary_match = re.search(r"一句话总结[:：](.+)", text)
        if summary_match:
            result.summary = summary_match.group(1).strip()

        return result
