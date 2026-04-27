import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from src.portfolio.parser import PortfolioParser


class TestPortfolioParser:
    def test_parse_holdings(self, tmp_path):
        md = tmp_path / "portfolio.md"
        md.write_text("""# 我的持仓

## 自选股

| 代码 | 名称 | 成本价 | 数量 | 板块 | 备注 |
|------|------|--------|------|------|------|
| 600519 | 贵州茅台 | 1700.0 | 100 | 白酒 | 长期持有 |
| 00700 | 腾讯控股 | 380.5 | 200 | 互联网 | 港股配置 |

## 关注板块

- 白酒
- 新能源

## 提醒设置

- 茅台：Q1 业绩窗口期
""", encoding="utf-8")

        parser = PortfolioParser(str(md))
        portfolio = parser.parse()

        assert len(portfolio.holdings) == 2
        assert portfolio.holdings[0].symbol == "600519"
        assert portfolio.holdings[0].name == "贵州茅台"
        assert portfolio.holdings[0].cost_price == 1700.0
        assert portfolio.holdings[0].quantity == 100
        assert portfolio.holdings[0].sector == "白酒"
        assert portfolio.holdings[0].notes == "长期持有"

        assert portfolio.holdings[1].symbol == "00700"
        assert portfolio.holdings[1].cost_price == 380.5

        assert portfolio.watch_sectors == ["白酒", "新能源"]
        assert portfolio.alerts == ["茅台：Q1 业绩窗口期"]

    def test_parse_missing_file(self):
        parser = PortfolioParser("/nonexistent/portfolio.md")
        portfolio = parser.parse()
        assert portfolio.holdings == []
        assert portfolio.watch_sectors == []

    def test_get_holding(self, tmp_path):
        md = tmp_path / "portfolio.md"
        md.write_text("""# 我的持仓

## 自选股

| 代码 | 名称 | 成本价 | 数量 | 板块 | 备注 |
|------|------|--------|------|------|------|
| 600519 | 贵州茅台 | 1700.0 | 100 | 白酒 | 长期持有 |
""", encoding="utf-8")

        parser = PortfolioParser(str(md))
        holding = parser.get_holding("600519")
        assert holding is not None
        assert holding.name == "贵州茅台"

        assert parser.get_holding("999999") is None

    def test_should_alert_up(self, tmp_path):
        md = tmp_path / "portfolio.md"
        md.write_text("""# 我的持仓

## 自选股

| 代码 | 名称 | 成本价 | 数量 | 板块 | 备注 |
|------|------|--------|------|------|------|
| 600519 | 贵州茅台 | 100.0 | 100 | 白酒 | 测试 |
""", encoding="utf-8")

        parser = PortfolioParser(str(md))
        triggered, msg = parser.should_alert("600519", 106.0)
        assert triggered is True
        assert "上涨 6.0%" in msg

    def test_should_alert_down(self, tmp_path):
        md = tmp_path / "portfolio.md"
        md.write_text("""# 我的持仓

## 自选股

| 代码 | 名称 | 成本价 | 数量 | 板块 | 备注 |
|------|------|--------|------|------|------|
| 600519 | 贵州茅台 | 100.0 | 100 | 白酒 | 测试 |
""", encoding="utf-8")

        parser = PortfolioParser(str(md))
        triggered, msg = parser.should_alert("600519", 94.0)
        assert triggered is True
        assert "下跌 6.0%" in msg

    def test_should_alert_no_trigger(self, tmp_path):
        md = tmp_path / "portfolio.md"
        md.write_text("""# 我的持仓

## 自选股

| 代码 | 名称 | 成本价 | 数量 | 板块 | 备注 |
|------|------|--------|------|------|------|
| 600519 | 贵州茅台 | 100.0 | 100 | 白酒 | 测试 |
""", encoding="utf-8")

        parser = PortfolioParser(str(md))
        triggered, msg = parser.should_alert("600519", 102.0)
        assert triggered is False
        assert msg == ""

    def test_should_alert_not_in_portfolio(self, tmp_path):
        md = tmp_path / "portfolio.md"
        md.write_text("""# 我的持仓

## 自选股

| 代码 | 名称 | 成本价 | 数量 | 板块 | 备注 |
|------|------|--------|------|------|------|
| 600519 | 贵州茅台 | 100.0 | 100 | 白酒 | 测试 |
""", encoding="utf-8")

        parser = PortfolioParser(str(md))
        triggered, msg = parser.should_alert("000001", 10.0)
        assert triggered is False
