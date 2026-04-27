import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from unittest.mock import MagicMock, patch

import pytest

from src.analysis.diagnosis import DiagnosisAnalyzer, DiagnosisResult
from src.analysis.morning_report import MorningReportGenerator
from src.data.fetcher import StockQuote, MarketSnapshot


class TestDiagnosisAnalyzer:
    def setup_method(self):
        self.mock_fetcher = MagicMock()
        self.mock_kimi = MagicMock()
        self.mock_portfolio = MagicMock()
        self.analyzer = DiagnosisAnalyzer(
            data_fetcher=self.mock_fetcher,
            kimi_client=self.mock_kimi,
            portfolio_parser=self.mock_portfolio,
        )

    def test_analyze_success(self):
        self.mock_fetcher.get_stock_quote.return_value = StockQuote(
            symbol="600519",
            name="贵州茅台",
            open=1700.0,
            high=1720.0,
            low=1690.0,
            close=1710.0,
            volume=50000,
            change_pct=1.2,
            source="tushare",
        )
        self.mock_fetcher.get_news.return_value = [
            {"title": "新闻1", "summary": "摘要1"}
        ]

        mock_holding = MagicMock()
        mock_holding.cost_price = 1600.0
        mock_holding.quantity = 100
        mock_holding.sector = "白酒"
        mock_holding.notes = "长期"
        mock_holding.name = "贵州茅台"
        self.mock_portfolio.get_holding.return_value = mock_holding
        self.mock_portfolio.should_alert.return_value = (False, "")

        self.mock_kimi.chat.return_value = """
## 综合评分：85/100
## 策略建议：进攻型
一句话总结：趋势向好，可继续持有

## 技术速览
- 趋势判断：上升趋势
- 关键价位：支撑 1680 元 / 压力 1750 元
- 止损参考：1650 元（-3%）

## 多派会诊
- 技术面：多头排列
- 基本面：稳健增长
- 资金面：北向流入
- 情绪面：乐观

## 操作建议
1. 持有观望
2. 突破 1750 可加仓
"""

        result = self.analyzer.analyze("600519", "贵州茅台")

        assert isinstance(result, DiagnosisResult)
        assert result.symbol == "600519"
        assert result.name == "贵州茅台"
        assert result.score == 85
        assert result.strategy == "进攻型"
        assert result.support == 1680.0
        assert result.resistance == 1750.0
        assert result.stop_loss == 1650.0
        assert result.alert_triggered is False

    def test_analyze_data_failed(self):
        self.mock_fetcher.get_stock_quote.return_value = StockQuote(
            symbol="600519",
            name="",
            source="failed",
            warnings=["数据暂不可用"],
        )

        result = self.analyzer.analyze("600519")

        assert result.source == "failed"
        assert "数据暂不可用" in result.warnings
        self.mock_kimi.chat.assert_not_called()

    def test_analyze_alert_triggered(self):
        self.mock_fetcher.get_stock_quote.return_value = StockQuote(
            symbol="600519",
            name="贵州茅台",
            close=106.0,
            volume=10000,
            change_pct=6.0,
            source="tushare",
        )
        self.mock_fetcher.get_news.return_value = []

        mock_holding = MagicMock()
        mock_holding.cost_price = 100.0
        mock_holding.quantity = 100
        mock_holding.sector = "白酒"
        mock_holding.notes = ""
        mock_holding.name = "贵州茅台"
        self.mock_portfolio.get_holding.return_value = mock_holding
        self.mock_portfolio.should_alert.return_value = (True, "贵州茅台(600519) 较成本价上涨 6.0%")

        self.mock_kimi.chat.return_value = "## 综合评分：70/100\n## 策略建议：防御型"

        result = self.analyzer.analyze("600519")

        assert result.alert_triggered is True
        assert "上涨 6.0%" in result.alert_msg

    def test_analyze_llm_empty(self):
        self.mock_fetcher.get_stock_quote.return_value = StockQuote(
            symbol="600519",
            name="贵州茅台",
            close=1710.0,
            volume=50000,
            change_pct=1.2,
            source="tushare",
        )
        self.mock_fetcher.get_news.return_value = []
        self.mock_portfolio.get_holding.return_value = None
        self.mock_kimi.chat.return_value = ""

        result = self.analyzer.analyze("600519")

        assert result.source == "failed"
        assert "AI 分析服务暂不可用" in result.warnings


class TestMorningReportGenerator:
    def setup_method(self):
        self.mock_fetcher = MagicMock()
        self.mock_kimi = MagicMock()
        self.mock_portfolio = MagicMock()
        self.generator = MorningReportGenerator(
            data_fetcher=self.mock_fetcher,
            kimi_client=self.mock_kimi,
            portfolio_parser=self.mock_portfolio,
        )

    def test_generate_success(self):
        from src.portfolio.parser import Holding, Portfolio

        self.mock_portfolio.parse.return_value = Portfolio(
            holdings=[
                Holding(symbol="600519", name="贵州茅台", cost_price=1700.0, quantity=100, sector="白酒", notes=""),
            ],
            watch_sectors=["白酒", "新能源"],
        )
        self.mock_fetcher.get_global_market.return_value = MarketSnapshot(
            dow_jones={"close": 35000, "change": 0.5},
            sp500={"close": 4500, "change": 0.3},
            nasdaq={"close": 14000, "change": 0.4},
            source="tushare",
        )
        self.mock_fetcher.get_news.return_value = [
            {"title": "茅台季报超预期", "summary": "Q1 营收增长"}
        ]

        self.mock_kimi.chat.return_value = "# 晨报 2024-04-26\n\n## 隔夜全球市场速览\n- 美股：上涨\n\n## 持仓个股重大事件\n- 茅台：季报超预期\n\n## 今日重点板块前瞻\n- 白酒：景气度回升"

        report = self.generator.generate()

        assert report.content is not None
        assert "晨报" in report.content
        assert report.source == "kimi"

    def test_generate_llm_failed(self):
        from src.portfolio.parser import Portfolio

        self.mock_portfolio.parse.return_value = Portfolio()
        self.mock_fetcher.get_global_market.return_value = MarketSnapshot(source="failed")
        self.mock_fetcher.get_news.return_value = []
        self.mock_kimi.chat.return_value = ""

        report = self.generator.generate()

        assert "晨报生成失败" in report.content
        assert report.source == "failed"
        assert "AI 分析服务暂不可用" in report.warnings
