"""portfolio.md 持仓文档解析器。"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger


@dataclass
class Holding:
    """单个持仓条目。"""

    symbol: str
    name: str
    cost_price: float | None = None
    quantity: int | None = None
    sector: str = ""
    notes: str = ""


@dataclass
class Portfolio:
    """用户持仓总览。"""

    holdings: list[Holding] = field(default_factory=list)
    watch_sectors: list[str] = field(default_factory=list)
    alerts: list[str] = field(default_factory=list)


class PortfolioParser:
    """解析 portfolio.md，提取持仓、关注板块和提醒。"""

    # 匹配持仓表格行：| 代码 | 名称 | 成本价 | 数量 | 板块 | 备注 |
    HOLDING_ROW_PATTERN = re.compile(
        r"\|\s*(\d{5,6})\s*\|\s*([^|]+?)\s*\|\s*([\d.]+|)\s*\|\s*(\d+|)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|"
    )

    def __init__(self, file_path: str | Path = "portfolio.md"):
        self.file_path = Path(file_path)

    def parse(self) -> Portfolio:
        """读取并解析 portfolio.md，返回 Portfolio 对象。"""
        if not self.file_path.exists():
            logger.warning("portfolio.md 不存在: {}", self.file_path)
            return Portfolio()

        try:
            content = self.file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error("读取 portfolio.md 失败: {}", e)
            return Portfolio()

        holdings = self._parse_holdings(content)
        watch_sectors = self._parse_watch_sectors(content)
        alerts = self._parse_alerts(content)

        logger.info(
            "解析 portfolio.md 完成: {} 只持仓, {} 个关注板块",
            len(holdings),
            len(watch_sectors),
        )
        return Portfolio(
            holdings=holdings,
            watch_sectors=watch_sectors,
            alerts=alerts,
        )

    def _parse_holdings(self, content: str) -> list[Holding]:
        """解析持仓表格。"""
        holdings = []
        for match in self.HOLDING_ROW_PATTERN.finditer(content):
            symbol = match.group(1).strip()
            name = match.group(2).strip()
            cost_str = match.group(3).strip()
            qty_str = match.group(4).strip()
            sector = match.group(5).strip()
            notes = match.group(6).strip()

            cost_price = float(cost_str) if cost_str else None
            quantity = int(qty_str) if qty_str else None

            holdings.append(
                Holding(
                    symbol=symbol,
                    name=name,
                    cost_price=cost_price,
                    quantity=quantity,
                    sector=sector,
                    notes=notes,
                )
            )
        return holdings

    def _parse_watch_sectors(self, content: str) -> list[str]:
        """解析 ## 关注板块 下的列表项。"""
        sectors = []
        in_section = False
        for line in content.splitlines():
            if "## 关注板块" in line:
                in_section = True
                continue
            if in_section:
                if line.startswith("## "):
                    break
                match = re.match(r"[-*]\s+(.+)", line.strip())
                if match:
                    sectors.append(match.group(1).strip())
        return sectors

    def _parse_alerts(self, content: str) -> list[str]:
        """解析 ## 提醒设置 下的列表项。"""
        alerts = []
        in_section = False
        for line in content.splitlines():
            if "## 提醒设置" in line:
                in_section = True
                continue
            if in_section:
                if line.startswith("## "):
                    break
                match = re.match(r"[-*]\s+(.+)", line.strip())
                if match:
                    alerts.append(match.group(1).strip())
        return alerts

    def get_holding(self, symbol: str) -> Holding | None:
        """根据代码获取单个持仓。"""
        portfolio = self.parse()
        for h in portfolio.holdings:
            if h.symbol == symbol:
                return h
        return None

    def should_alert(self, symbol: str, current_price: float) -> tuple[bool, str]:
        """检查持仓是否触发 ±5% 成本价警示。"""
        holding = self.get_holding(symbol)
        if not holding or holding.cost_price is None:
            return False, ""

        cost = holding.cost_price
        change_pct = (current_price - cost) / cost * 100

        if abs(change_pct) >= 5:
            direction = "上涨" if change_pct > 0 else "下跌"
            msg = f"{holding.name}({symbol}) 较成本价{direction} {abs(change_pct):.1f}%"
            return True, msg

        return False, ""
