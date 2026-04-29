"""晨报生成器：整合全球市场、持仓事件、板块前瞻。"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from loguru import logger

from src.core.models import KimiRawData
from src.data.fetcher import DataFetcher
from src.data.kimi_adapter import KimiAdapter
from src.llm.claude_code_client import ClaudeCodeClient
from src.llm.kimi_agent_browser import KimiAgentBrowser, KimiFormatError, KimiLoginError, KimiTimeoutError
from src.llm.kimi_report_prompt import build_kimi_prompt
from src.llm.prompts import MORNING_REPORT_SYSTEM, build_morning_report_prompt
from src.portfolio.parser import Portfolio, PortfolioParser
from config.settings import get_settings


@dataclass
class MorningReport:
    """晨报结果。"""

    date: str
    content: str
    source: str = "kimi"
    warnings: list[str] = field(default_factory=list)
    # 模块执行状态跟踪
    module_status: dict[str, str] = field(default_factory=dict)
    # Kimi 原始数据与情绪信息
    kimi_raw: dict = field(default_factory=dict)
    sentiment: dict | None = None


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
        settings = get_settings()
        cookie_path = settings.kimi_agent.cookie_path if settings.kimi_agent.agent_enabled else ""
        self.kimi_agent = KimiAgentBrowser(cookie_path=cookie_path) if cookie_path else None
        self.kimi_adapter = KimiAdapter()
        self.kimi_fixed_wait = settings.kimi_agent.fixed_wait_sec

    def generate(self) -> MorningReport:
        """生成完整晨报，主路径优先使用 Kimi Agent，失败则降级到 Claude Fallback。"""
        today = date.today().strftime("%Y-%m-%d")
        logger.info("开始生成晨报（主路径）: {}", today)
        module_status: dict[str, str] = {}
        warnings: list[str] = []
        kimi_raw: dict = {}
        sentiment: dict | None = None
        content = ""
        source = "kimi"
        kimi_source = ""
        generation_elapsed_sec = None

        # 1. 数据预准备
        try:
            portfolio = self.portfolio.parse()
            module_status["数据预准备"] = "成功"
        except Exception as e:
            module_status["数据预准备"] = f"失败: {e}"
            logger.error("晨报数据预准备失败: {}", e)
            return MorningReport(
                date=today,
                content="晨报生成失败：无法读取持仓数据。",
                warnings=[f"持仓解析异常: {e}"],
                source="failed",
                module_status=module_status,
            )

        # 2. 检查本地缓存
        cache_dir = Path("data/cache/kimi_report")
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"{today}.md"

        if cache_file.exists():
            logger.info("命中本地缓存: {}", cache_file)
            try:
                content = cache_file.read_text(encoding="utf-8")
                module_status["Kimi Agent 生成"] = "成功（缓存）"
                # 尝试从缓存内容提取情绪（适配器可能支持）
                sentiment = self._extract_sentiment(content)
                if sentiment:
                    module_status["情绪提取"] = "成功"
                else:
                    module_status["情绪提取"] = "跳过（无情绪数据）"
                module_status["MD 格式校验"] = "成功"
                return MorningReport(
                    date=today,
                    content=content,
                    source="kimi_cache",
                    warnings=warnings,
                    module_status=module_status,
                    sentiment=sentiment,
                )
            except Exception as e:
                logger.warning("读取缓存失败，继续生成: {}", e)
                module_status["Kimi Agent 生成"] = f"缓存读取失败: {e}"

        # 3. 调用 Kimi Agent 生成
        kimi_ok = False
        if not content and self.kimi_agent:
            try:
                # 获取全球市场数据
                market = None
                try:
                    market = self.data_fetcher.get_global_market()
                except Exception as e:
                    logger.warning("获取全球市场数据失败: {}", e)

                # 获取持仓个股新闻
                holdings_news = {}
                for holding in portfolio.holdings:
                    try:
                        news = self.data_fetcher.get_news(holding.symbol)
                        if news:
                            holdings_news[holding.symbol] = news
                    except Exception:
                        pass

                # 组装 input_data
                yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
                input_data = {
                    "date": today,
                    "yesterday": yesterday,
                    "market_snapshot": {
                        "dow_jones": {"close": market.dow_jones.get("close", "N/A"), "change": market.dow_jones.get("change", "N/A")} if market and market.dow_jones else None,
                        "sp500": {"close": market.sp500.get("close", "N/A"), "change": market.sp500.get("change", "N/A")} if market and market.sp500 else None,
                        "nasdaq": {"close": market.nasdaq.get("close", "N/A"), "change": market.nasdaq.get("change", "N/A")} if market and market.nasdaq else None,
                        "hsi_futures": {"close": market.hsi_futures.get("close", "N/A"), "change": market.hsi_futures.get("change", "N/A")} if market and market.hsi_futures else None,
                        "usdx": {"close": market.usdx.get("close", "N/A"), "change": market.usdx.get("change", "N/A")} if market and market.usdx else None,
                        "usdcnh": {"close": market.usdcnh.get("close", "N/A"), "change": market.usdcnh.get("change", "N/A")} if market and market.usdcnh else None,
                        "us_10y": {"close": market.us_10y.get("close", "N/A"), "change": market.us_10y.get("change", "N/A")} if market and market.us_10y else None,
                    },
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
                    "holdings_news": {
                        sym: [{"title": n.get("title", ""), "summary": n.get("summary", "")[:150]} for n in items]
                        for sym, items in holdings_news.items()
                    },
                    "fetch_time": datetime.now().strftime("%H:%M"),
                }

                start_time = datetime.now()
                # async 方法在 sync 上下文中运行
                raw_result = asyncio.run(
                    self.kimi_agent.generate_report(
                        input_data, fixed_wait_sec=self.kimi_fixed_wait
                    )
                )
                elapsed = (datetime.now() - start_time).total_seconds()
                generation_elapsed_sec = int(elapsed)

                if not raw_result.get("success"):
                    error_msg = raw_result.get("error", "未知错误")
                    raise KimiFormatError(f"Kimi 生成失败: {error_msg}")

                # 保存原始数据
                kimi_raw = {
                    "raw_markdown": raw_result.get("markdown", ""),
                    "elapsed_sec": raw_result.get("elapsed_sec", 0),
                }

                # 使用适配器清洗和验证
                cleaned = self.kimi_adapter.clean_markdown(raw_result.get("markdown", ""))
                validated = self.kimi_adapter.validate_report(cleaned)
                if not validated:
                    raise KimiFormatError("Kimi 返回内容未通过 Markdown 格式校验")

                content = cleaned
                module_status["Kimi Agent 生成"] = "成功"
                module_status["MD 格式校验"] = "成功"
                kimi_ok = True

                # 提取情绪数据
                sentiment = self._extract_sentiment(content)
                if sentiment:
                    module_status["情绪提取"] = "成功"
                else:
                    module_status["情绪提取"] = "跳过（未识别到情绪数据）"

                # 保存到本地缓存
                cache_file.write_text(content, encoding="utf-8")
                logger.info("Kimi 晨报已缓存: {}", cache_file)

                # 保存原始数据到 SQLite
                KimiRawData.create(
                    data_date=today,
                    task_type="report",
                    content=kimi_raw.get("raw_markdown", ""),
                    fetch_time=datetime.now(),
                    status="success",
                    elapsed_sec=generation_elapsed_sec,
                    sentiment_mood=sentiment.get("mood") if sentiment else None,
                    sentiment_score=sentiment.get("score") if sentiment else None,
                )

            except (KimiTimeoutError, KimiLoginError, KimiFormatError) as e:
                module_status["Kimi Agent 生成"] = f"失败: {e}"
                module_status["MD 格式校验"] = "失败"
                module_status["情绪提取"] = "失败"
                warnings.append(f"Kimi 生成异常: {e}")
                logger.warning("Kimi Agent 生成失败，准备降级: {}", e)

                # 记录失败原始数据
                try:
                    KimiRawData.create(
                        data_date=today,
                        task_type="error",
                        content=kimi_raw.get("raw_markdown", ""),
                        fetch_time=datetime.now(),
                        status="failed",
                        error_msg=str(e),
                        elapsed_sec=generation_elapsed_sec,
                    )
                except Exception as db_err:
                    logger.warning("保存 Kimi 错误日志失败: {}", db_err)

            except Exception as e:
                module_status["Kimi Agent 生成"] = f"失败: {e}"
                module_status["MD 格式校验"] = "失败"
                module_status["情绪提取"] = "失败"
                warnings.append(f"Kimi 未知异常: {e}")
                logger.warning("Kimi Agent 未知异常，准备降级: {}", e)
        elif not content and not self.kimi_agent:
            module_status["Kimi Agent 生成"] = "跳过（未启用）"
            logger.info("Kimi Agent 未启用，直接降级到 Claude Fallback")

        # 4. 降级到 Claude Fallback
        if not content:
            logger.info("降级到 Claude Fallback 生成晨报")
            fallback_report = self.generate_fallback()
            # 合并状态
            module_status.update(fallback_report.module_status)
            module_status["降级来源"] = "claude_fallback"
            return MorningReport(
                date=today,
                content=fallback_report.content,
                source="claude_fallback",
                warnings=fallback_report.warnings + warnings,
                module_status=module_status,
                kimi_raw=kimi_raw,
                sentiment=sentiment,
            )

        # 5. 替换日期占位符
        content = content.replace("YYYY-MM-DD", today)

        logger.info("晨报生成完成（Kimi 主路径）: {} 模块状态: {}", today, module_status)
        return MorningReport(
            date=today,
            content=content,
            source=source,
            warnings=warnings,
            module_status=module_status,
            kimi_raw=kimi_raw,
            sentiment=sentiment,
        )

    def generate_fallback(self) -> MorningReport:
        """降级生成晨报，使用 Claude Code CLI（原 generate 逻辑）。"""
        today = date.today().strftime("%Y-%m-%d")
        logger.info("开始生成晨报（Claude Fallback）: {}", today)
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

        logger.info("晨报生成完成（Claude Fallback）: {} 模块状态: {}", today, module_status)
        return MorningReport(
            date=today,
            content=content,
            warnings=warnings,
            module_status=module_status,
        )

    def _extract_sentiment(self, content: str) -> dict | None:
        """从晨报内容中提取情绪数据。

        优先查找 Markdown 中的情绪元数据块，例如：
        <!-- sentiment: {"mood": "乐观", "score": 75} -->
        或适配器返回的结构化数据。
        """
        try:
            # 尝试从 HTML 注释中提取
            import re

            match = re.search(r"<!--\s*sentiment:\s*(\{.*?\})\s*-->", content)
            if match:
                data = json.loads(match.group(1))
                if "mood" in data and "score" in data:
                    return {"mood": data["mood"], "score": int(data["score"])}
        except Exception:
            pass

        # 尝试通过适配器提取
        try:
            sentiment = self.kimi_adapter.extract_sentiment(content)
            if sentiment and "mood" in sentiment:
                return sentiment
        except Exception:
            pass

        return None
