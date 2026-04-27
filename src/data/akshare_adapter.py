"""AKShare 备用数据源封装。"""

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

    def _is_hk(self, symbol: str) -> bool:
        return ".HK" in symbol.upper()

    def get_daily_quote(self, symbol: str) -> dict:
        """获取个股行情，返回标准化 dict。"""
        ak = self._get_ak()
        try:
            if self._is_hk(symbol):
                # 港股
                hk_code = symbol.upper().replace(".HK", "")
                df = ak.stock_hk_hist(symbol=hk_code, period="daily", start_date="", end_date="", adjust="")
            else:
                # A股
                df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date="", end_date="", adjust="")

            if df is None or df.empty:
                return {}

            row = df.iloc[-1]
            return {
                "symbol": symbol,
                "name": str(row.get("名称", "")) if "名称" in row else "",
                "open": float(row.get("开盘", 0)) if row.get("开盘") is not None else None,
                "high": float(row.get("最高", 0)) if row.get("最高") is not None else None,
                "low": float(row.get("最低", 0)) if row.get("最低") is not None else None,
                "close": float(row.get("收盘", 0)) if row.get("收盘") is not None else None,
                "volume": int(row.get("成交量", 0)) if row.get("成交量") is not None else 0,
                "turnover": float(row.get("换手率", 0)) if row.get("换手率") is not None else None,
                "change_pct": float(row.get("涨跌幅", 0)) if row.get("涨跌幅") is not None else None,
                "source": "akshare",
                "trade_date": str(row.get("日期", "")),
            }
        except Exception as e:
            logger.error("AKShare 获取行情失败 ({}): {}", symbol, e)
            return {}

    def get_global_market(self) -> dict:
        """获取全球市场数据。"""
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

        try:
            # 美股指数
            try:
                df_us = ak.index_us_spot()
                if df_us is not None and not df_us.empty:
                    for _, row in df_us.iterrows():
                        name = str(row.get("名称", "")).lower()
                        if "道琼" in name or "dow" in name:
                            result["dow_jones"] = {
                                "close": row.get("最新价"),
                                "change": row.get("涨跌幅"),
                            }
                        elif "标普" in name or "s&p" in name:
                            result["sp500"] = {
                                "close": row.get("最新价"),
                                "change": row.get("涨跌幅"),
                            }
                        elif "纳斯" in name or "nasdaq" in name:
                            result["nasdaq"] = {
                                "close": row.get("最新价"),
                                "change": row.get("涨跌幅"),
                            }
            except Exception as e:
                logger.debug("AKShare 美股指数获取失败: {}", e)

            # 外汇（美元指数、离岸人民币）
            try:
                df_fx = ak.fx_spot_quote()
                if df_fx is not None and not df_fx.empty:
                    for _, row in df_fx.iterrows():
                        name = str(row.get("名称", ""))
                        if "USD" in name and "CNH" in name:
                            result["usdcnh"] = {
                                "close": row.get("最新价"),
                                "change": row.get("涨跌幅"),
                            }
                        elif "美元指数" in name or "DXY" in name:
                            result["usdx"] = {
                                "close": row.get("最新价"),
                                "change": row.get("涨跌幅"),
                            }
            except Exception as e:
                logger.debug("AKShare 外汇获取失败: {}", e)

            # 恒生期货
            try:
                df_hk = ak.futures_hk_spot()
                if df_hk is not None and not df_hk.empty:
                    for _, row in df_hk.iterrows():
                        name = str(row.get("名称", ""))
                        if "恒生" in name or "HSI" in name:
                            result["hsi_futures"] = {
                                "close": row.get("最新价"),
                                "change": row.get("涨跌幅"),
                            }
                            break
            except Exception as e:
                logger.debug("AKShare 恒生期货获取失败: {}", e)

            # 美债收益率
            try:
                df_bond = ak.bond_us_treasury()
                if df_bond is not None and not df_bond.empty:
                    row = df_bond.iloc[0]
                    result["us_10y"] = {
                        "close": row.get("收益率", row.get("close")),
                        "change": row.get("涨跌", row.get("change")),
                    }
            except Exception as e:
                logger.debug("AKShare 美债获取失败: {}", e)

        except Exception as e:
            logger.error("AKShare 获取全球市场数据失败: {}", e)

        return result

    def get_news(self, symbol: str) -> list[dict]:
        """获取个股新闻。"""
        ak = self._get_ak()
        try:
            df = ak.stock_news_em(symbol=symbol)
            if df is None or df.empty:
                return []

            news = []
            for _, row in df.head(5).iterrows():
                news.append({
                    "title": str(row.get("标题", "")),
                    "summary": str(row.get("内容", "")),
                    "publish_time": str(row.get("发布时间", "")),
                    "source": "akshare",
                })
            return news
        except Exception as e:
            logger.error("AKShare 获取新闻失败 ({}): {}", symbol, e)
            return []
