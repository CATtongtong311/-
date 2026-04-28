"""iTick 备用数据源封装。

免费版限制：每分钟 5 次调用
Base URL: https://api-free.itick.org
认证: Header token

支持市场：
- A股: region=sz/sh, code=6位数字
- 港股: region=hk, code=纯数字(不带.HK和前导零)
- 指数: region=us, code=... (待确认)
"""

import time
from datetime import datetime
from pathlib import Path

import requests
from loguru import logger

from config.settings import get_settings


class ItickAdapter:
    """iTick API 备用数据源适配器。"""

    BASE_URL = "https://api-free.itick.org"
    RATE_LIMIT = 5  # 每分钟最大调用次数
    RATE_WINDOW = 60  # 秒

    def __init__(self, token: str = ""):
        settings = get_settings()
        self.token = token or getattr(settings.data_source, "itick_token", "")
        self._call_times: list[float] = []  # 记录每次调用时间戳
        self._session = requests.Session()
        self._session.headers.update({
            "accept": "application/json",
            "token": self.token,
        })

    def _wait_for_rate_limit(self) -> None:
        """等待速率限制，确保每分钟不超过 5 次。"""
        now = time.time()
        # 清理 60 秒前的记录
        self._call_times = [t for t in self._call_times if now - t < self.RATE_WINDOW]
        if len(self._call_times) >= self.RATE_LIMIT:
            wait = self.RATE_WINDOW - (now - self._call_times[0]) + 1
            if wait > 0:
                logger.debug("iTick 速率限制等待 {} 秒", wait)
                time.sleep(wait)
            self._call_times = []

    def _call(self, endpoint: str, params: dict) -> dict | None:
        """调用 iTick API，返回 data 字段。"""
        self._wait_for_rate_limit()
        url = f"{self.BASE_URL}{endpoint}"
        try:
            resp = self._session.get(url, params=params, timeout=15)
            self._call_times.append(time.time())
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") != 0:
                logger.warning("iTick API 返回错误: {} {}", result.get("code"), result.get("msg"))
                return None
            return result.get("data")
        except requests.RequestException as e:
            logger.warning("iTick API 请求失败: {}", e)
            return None

    @staticmethod
    def _a_share_region(code: str) -> str:
        """A股代码判断交易所。"""
        c = code.strip()
        if c.startswith(("60", "68", "9")):
            return "sh"
        return "sz"

    @staticmethod
    def _hk_code(code: str) -> str:
        """港股代码去掉 .HK 和前导零。"""
        return code.upper().replace(".HK", "").lstrip("0")

    def get_daily_quote(self, symbol: str) -> dict:
        """获取个股行情，返回标准化 dict。"""
        result = {
            "symbol": symbol,
            "name": "",
            "open": None,
            "high": None,
            "low": None,
            "close": None,
            "volume": 0,
            "turnover": None,
            "change_pct": None,
            "source": "itick",
            "trade_date": "",
        }

        # 1. 实时报价
        if ".HK" in symbol.upper():
            region = "hk"
            code = self._hk_code(symbol)
        else:
            region = self._a_share_region(symbol)
            code = symbol.strip()

        tick = self._call("/stock/tick", {"region": region, "code": code})
        if tick is None:
            logger.warning("iTick 获取行情失败: {}", symbol)
            return {}

        result["close"] = float(tick.get("ld", 0)) if tick.get("ld") else None
        result["volume"] = int(tick.get("v", 0)) if tick.get("v") else 0
        ts = tick.get("t")
        if ts:
            result["trade_date"] = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")

        # 2. 日线K线（取最近两天计算涨跌幅和 OHLC）
        kline = self._call("/stock/kline", {"region": region, "code": code, "kType": 8})
        if kline and isinstance(kline, list) and len(kline) >= 1:
            last = kline[-1]
            result["open"] = float(last.get("o", 0))
            result["high"] = float(last.get("h", 0))
            result["low"] = float(last.get("l", 0))
            if result["close"] is None:
                result["close"] = float(last.get("c", 0))
            result["volume"] = int(last.get("v", 0))
            result["turnover"] = float(last.get("tu", 0))

            if len(kline) >= 2:
                prev_close = float(kline[-2].get("c", 0))
                if prev_close > 0 and result["close"]:
                    result["change_pct"] = round((result["close"] - prev_close) / prev_close * 100, 2)

        # 3. 标的基本信息（获取名称）
        base = self._call("/stock/base", {"region": region, "code": code})
        if base:
            result["name"] = base.get("nc", "")

        if result["close"] is None:
            return {}
        return result

    def get_global_market(self) -> dict:
        """获取全球市场数据（美股三大指数）。"""
        result = {
            "dow_jones": None,
            "sp500": None,
            "nasdaq": None,
            "hsi_futures": None,
            "usdx": None,
            "usdcnh": None,
            "us_10y": None,
            "source": "itick",
        }

        # 美股三大指数
        indices = [
            ("dow_jones", "us", "DJI"),
            ("sp500", "us", "SPX"),
            ("nasdaq", "us", "IXIC"),
        ]
        for key, region, code in indices:
            tick = self._call("/indices/tick", {"region": region, "code": code})
            if tick:
                result[key] = {
                    "close": float(tick.get("ld", 0)) if tick.get("ld") else None,
                }

        return result
