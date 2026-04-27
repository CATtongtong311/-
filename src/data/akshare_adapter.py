"""AKShare 备用数据源封装。

接口选择策略（基于宿主机代理环境的稳定性测试）：
- A股最新价/名称：stock_individual_info_em（东财，稳定）
- A股历史日线：stock_zh_a_daily（新浪，稳定）
- 港股历史日线：stock_hk_daily（新浪，稳定，最新价取自最后一条）
- 个股新闻：stock_news_em（东财，稳定）
- 美股指数：index_us_stock_sina（新浪）
- 美债收益率：bond_zh_us_rate（新浪）
"""

from datetime import datetime

from loguru import logger


class AkshareAdapter:
    """AKShare 备用数据源适配器。"""

    def __init__(self):
        self._ak = None

    def _get_ak(self):
        """懒加载 akshare。"""
        if self._ak is None:
            import akshare as ak
            self._ak = ak
        return self._ak

    @staticmethod
    def _is_hk(symbol: str) -> bool:
        return ".HK" in symbol.upper()

    @staticmethod
    def _a_share_prefix(symbol: str) -> str:
        """A股代码加交易所前缀（新浪接口要求）。"""
        code = symbol.strip()
        if code.startswith(("60", "68", "9")):
            return f"sh{code}"
        return f"sz{code}"

    def get_daily_quote(self, symbol: str) -> dict:
        """获取个股行情，返回标准化 dict。"""
        ak = self._get_ak()
        if self._is_hk(symbol):
            return self._get_hk_quote(symbol, ak)
        return self._get_a_quote(symbol, ak)

    def _get_a_quote(self, symbol: str, ak) -> dict:
        """A股：东财获取最新价/名称，新浪获取日线算涨跌幅。"""
        code = symbol.strip()
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
            "source": "akshare",
            "trade_date": "",
        }

        # 1) 东财：最新价 + 股票名称 + 流通股本（用于换手率），带重试
        for attempt in range(2):
            try:
                info = ak.stock_individual_info_em(symbol=code)
                kv = {row["item"]: row["value"] for _, row in info.iterrows()}
                result["name"] = str(kv.get("股票简称", ""))
                latest_price = kv.get("最新")
                if latest_price is not None:
                    result["close"] = float(latest_price)
                break
            except Exception as e:
                logger.warning("AKShare 东财个股信息获取失败 ({}), 尝试 {}/2: {}", symbol, attempt + 1, e)
                if attempt == 0:
                    import time
                    time.sleep(1.5)

        # 2) 新浪：历史日线（取最后两天计算涨跌幅，今天 OHLC）
        try:
            sina_symbol = self._a_share_prefix(code)
            df = ak.stock_zh_a_daily(symbol=sina_symbol)
            if df is None or df.empty:
                if not result["close"]:
                    logger.error("AKShare 获取行情失败 ({}): 数据为空", symbol)
                    return {}
            else:
                last = df.iloc[-1]
                result["trade_date"] = str(last.get("date", ""))
                result["open"] = float(last.get("open", 0)) if last.get("open") is not None else None
                result["high"] = float(last.get("high", 0)) if last.get("high") is not None else None
                result["low"] = float(last.get("low", 0)) if last.get("low") is not None else None
                if not result["close"]:
                    result["close"] = float(last.get("close", 0))
                result["volume"] = int(last.get("volume", 0)) if last.get("volume") is not None else 0

                # 涨跌幅：以东财最新价 / 新浪日线最后一天收盘价 与 前一天收盘价 比较
                if len(df) >= 2:
                    prev_close = float(df.iloc[-2].get("close", 0))
                    if prev_close > 0 and result["close"]:
                        result["change_pct"] = round((result["close"] - prev_close) / prev_close * 100, 2)
                if last.get("turnover") is not None:
                    result["turnover"] = round(float(last.get("turnover")) * 100, 2)
        except Exception as e:
            logger.error("AKShare 新浪日线获取失败 ({}): {}", symbol, e)
            if not result["close"]:
                return {}

        return result if result["close"] else {}

    def _get_hk_quote(self, symbol: str, ak) -> dict:
        """港股：新浪历史日线（最新价 = 最后一条收盘价）。"""
        hk_code = symbol.upper().replace(".HK", "").lstrip("0").rjust(5, "0")
        try:
            df = ak.stock_hk_daily(symbol=hk_code)
            if df is None or df.empty:
                return {}
            last = df.iloc[-1]
            close = float(last.get("close", 0))
            change_pct = None
            if len(df) >= 2:
                prev_close = float(df.iloc[-2].get("close", 0))
                if prev_close > 0:
                    change_pct = round((close - prev_close) / prev_close * 100, 2)
            return {
                "symbol": symbol,
                "name": "",
                "open": float(last.get("open", 0)) if last.get("open") is not None else None,
                "high": float(last.get("high", 0)) if last.get("high") is not None else None,
                "low": float(last.get("low", 0)) if last.get("low") is not None else None,
                "close": close,
                "volume": int(last.get("volume", 0)) if last.get("volume") is not None else 0,
                "turnover": None,
                "change_pct": change_pct,
                "source": "akshare",
                "trade_date": str(last.get("date", "")),
            }
        except Exception as e:
            logger.error("AKShare 港股行情获取失败 ({}): {}", symbol, e)
            return {}

    def get_global_market(self) -> dict:
        """获取全球市场数据（美股三大指数 + 美债 10Y）。"""
        ak = self._get_ak()
        result = {
            "dow_jones": None,
            "sp500": None,
            "nasdaq": None,
            "hsi_futures": None,
            "usdx": None,
            "usdcnh": None,
            "us_10y": None,
            "source": "akshare",
        }

        # 美股三大指数（新浪）
        for key, symbol in [("dow_jones", ".DJI"), ("sp500", ".INX"), ("nasdaq", ".IXIC")]:
            try:
                df = ak.index_us_stock_sina(symbol=symbol)
                if df is not None and not df.empty:
                    last = df.iloc[-1]
                    close = float(last.get("close", 0))
                    change_pct = None
                    if len(df) >= 2:
                        prev = float(df.iloc[-2].get("close", 0))
                        if prev > 0:
                            change_pct = round((close - prev) / prev * 100, 2)
                    result[key] = {"close": close, "change": change_pct}
            except Exception as e:
                logger.debug("AKShare 美股指数 {} 获取失败: {}", symbol, e)

        # 美债收益率
        try:
            df_bond = ak.bond_zh_us_rate()
            if df_bond is not None and not df_bond.empty:
                row = df_bond.iloc[-1]
                us_10y = row.get("美国国债收益率10年", row.get("美国债收益率10年"))
                if us_10y is not None:
                    result["us_10y"] = {"close": float(us_10y), "change": None}
        except Exception as e:
            logger.debug("AKShare 美债获取失败: {}", e)

        return result

    def get_news(self, symbol: str) -> list[dict]:
        """获取个股新闻（东财，稳定）。"""
        ak = self._get_ak()
        code = symbol.upper().replace(".HK", "")
        try:
            df = ak.stock_news_em(symbol=code)
            if df is None or df.empty:
                return []
            news = []
            for _, row in df.head(5).iterrows():
                news.append({
                    "title": str(row.get("新闻标题", row.get("标题", ""))),
                    "summary": str(row.get("新闻内容", row.get("内容", "")))[:200],
                    "publish_time": str(row.get("发布时间", "")),
                    "source": "akshare",
                })
            return news
        except Exception as e:
            logger.error("AKShare 获取新闻失败 ({}): {}", symbol, e)
            return []
