"""Tushare Pro 数据源封装。"""

import tushare as ts
from loguru import logger

from src.data.quota import QuotaManager


class TushareAdapter:
    """Tushare 主数据源适配器。"""

    def __init__(self, token: str, quota: QuotaManager | None = None):
        self.token = token
        self.quota = quota
        self._pro = None

    def _get_pro(self):
        """懒加载 tushare pro_api。"""
        if self._pro is None:
            self._pro = ts.pro_api(self.token)
        return self._pro

    def _normalize_symbol(self, symbol: str) -> str:
        """将 6 位代码转为 Tushare 的 ts_code 格式。"""
        symbol = symbol.strip()
        if ".HK" in symbol.upper():
            # 港股格式: 00700.HK
            return symbol.upper()
        if len(symbol) == 6 and symbol.isdigit():
            first = symbol[0]
            if first == "6":
                return f"{symbol}.SH"
            elif first in "03":
                return f"{symbol}.SZ"
            elif first in "48":
                return f"{symbol}.BJ"
        return symbol

    def get_daily_quote(self, symbol: str) -> dict:
        """获取个股日线行情，返回标准化 dict。"""
        endpoint = "daily"
        if self.quota and not self.quota.check(endpoint):
            logger.warning("Tushare 额度不足，跳过调用")
            return {}

        ts_code = self._normalize_symbol(symbol)
        try:
            pro = self._get_pro()
            df = pro.daily(ts_code=ts_code, limit=1)

            if df is None or df.empty:
                if self.quota:
                    self.quota.record(endpoint, success=False)
                return {}

            row = df.iloc[0]
            result = {
                "symbol": symbol,
                "name": "",
                "open": float(row.get("open", 0)) if row.get("open") is not None else None,
                "high": float(row.get("high", 0)) if row.get("high") is not None else None,
                "low": float(row.get("low", 0)) if row.get("low") is not None else None,
                "close": float(row.get("close", 0)) if row.get("close") is not None else None,
                "volume": int(row.get("vol", 0)) if row.get("vol") is not None else 0,
                "turnover": None,
                "change_pct": None,
                "source": "tushare",
                "trade_date": str(row.get("trade_date", "")),
            }

            # 尝试计算涨跌幅
            try:
                pre_close = row.get("pre_close")
                close = row.get("close")
                if pre_close is not None and close is not None and pre_close != 0:
                    result["change_pct"] = round((close - pre_close) / pre_close * 100, 2)
            except Exception:
                pass

            if self.quota:
                self.quota.record(endpoint, success=True)
            return result
        except Exception as e:
            logger.error("Tushare 获取行情失败 ({}): {}", symbol, e)
            if self.quota:
                self.quota.record(endpoint, success=False)
            return {}

    def get_global_market(self) -> dict:
        """获取全球市场数据。"""
        endpoint = "index_global"
        if self.quota and not self.quota.check(endpoint):
            return {}

        result = {
            "dow_jones": None,
            "sp500": None,
            "nasdaq": None,
            "hsi_futures": None,
            "usdx": None,
            "usdcnh": None,
            "us_10y": None,
            "source": "tushare",
        }

        try:
            pro = self._get_pro()
            # 美股三大指数
            df = pro.index_global(limit=5)
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    name = str(row.get("name", "")).lower()
                    close = row.get("close")
                    change = row.get("change")
                    if "dow" in name or "道琼" in name:
                        result["dow_jones"] = {"close": close, "change": change}
                    elif "s&p" in name or "标普" in name:
                        result["sp500"] = {"close": close, "change": change}
                    elif "nasdaq" in name or "纳斯" in name:
                        result["nasdaq"] = {"close": close, "change": change}

            if self.quota:
                self.quota.record(endpoint, success=True)
        except Exception as e:
            logger.error("Tushare 获取全球市场数据失败: {}", e)
            if self.quota:
                self.quota.record(endpoint, success=False)

        return result

    def get_news(self, symbol: str) -> list[dict]:
        """获取个股相关公告/新闻。"""
        endpoint = "major_news"
        if self.quota and not self.quota.check(endpoint):
            return []

        try:
            pro = self._get_pro()
            # 尝试 major_news 接口
            df = pro.major_news(src="sina", start_date="", end_date="")
            if df is None or df.empty:
                if self.quota:
                    self.quota.record(endpoint, success=False)
                return []

            news = []
            for _, row in df.head(5).iterrows():
                news.append({
                    "title": str(row.get("title", "")),
                    "summary": str(row.get("content", "")),
                    "publish_time": str(row.get("datetime", "")),
                    "source": "tushare",
                })

            if self.quota:
                self.quota.record(endpoint, success=True)
            return news
        except Exception as e:
            logger.error("Tushare 获取新闻失败 ({}): {}", symbol, e)
            if self.quota:
                self.quota.record(endpoint, success=False)
            return []
