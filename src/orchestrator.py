"""中央调度器：整合飞书消息、诊股分析、晨报生成和卡片发送。"""

import asyncio
import json
from datetime import date
from pathlib import Path

from loguru import logger

from src.analysis.diagnosis import DiagnosisAnalyzer
from src.analysis.morning_report import MorningReport, MorningReportGenerator
from src.cards.diagnosis_card import DiagnosisCardBuilder
from src.cards.morning_report_card import MorningReportCardBuilder
from src.core.models import DiagnosisHistory, KimiRawData, MorningReportRecord
from src.data.fetcher import DataFetcher
from src.data.kimi_adapter import KimiAdapter
from src.feishu.card_sender import CardSender
from src.feishu.message_parser import MessageParser
from src.llm.claude_code_client import ClaudeCodeClient
from src.llm.kimi_agent_browser import KimiAgentBrowser
from src.portfolio.parser import PortfolioParser


class BotOrchestrator:
    """机器人物流调度中心：处理用户消息、生成分析、发送卡片。"""

    def __init__(self, settings):
        self.settings = settings

        # 数据层
        self.data_fetcher = DataFetcher(tushare_token=settings.data_source.token)

        # LLM 层（Claude Code CLI 替代 Kimi HTTP API）
        self.claude = ClaudeCodeClient()

        # Kimi Agent 浏览器层（条件初始化）
        self.kimi_browser = None
        if settings.kimi_agent.agent_enabled:
            try:
                self.kimi_browser = KimiAgentBrowser(
                    cookie_path=settings.kimi_agent.cookie_path,
                    headless=True,
                )
                logger.info("KimiAgentBrowser 已初始化")
            except Exception as e:
                logger.warning("KimiAgentBrowser 初始化失败: {}", e)

        # 分析层
        self.diagnosis_analyzer = DiagnosisAnalyzer(
            data_fetcher=self.data_fetcher,
            llm_client=self.claude,
            portfolio_parser=PortfolioParser(),
        )
        self.morning_report_generator = MorningReportGenerator(
            data_fetcher=self.data_fetcher,
            llm_client=self.claude,
            portfolio_parser=PortfolioParser(),
        )

        # 卡片层
        self.diagnosis_card_builder = DiagnosisCardBuilder()
        self.morning_report_card_builder = MorningReportCardBuilder()

        # 发送层
        self.sender = CardSender(
            app_id=settings.feishu.app_id,
            app_secret=settings.feishu.app_secret,
        )

        # 解析器
        self.message_parser = MessageParser()

    def handle_message(self, payload: dict) -> None:
        """处理飞书消息事件。"""
        chat_id = payload.get("chat_id", "")
        content = payload.get("content", "")
        message_type = payload.get("message_type", "")

        if message_type != "text":
            logger.debug("忽略非文本消息: type={}", message_type)
            return

        # 解析文本内容
        try:
            import json
            text_content = json.loads(content).get("text", "")
        except (json.JSONDecodeError, AttributeError):
            text_content = content

        # 解析用户输入
        parse_result = self.message_parser.parse(text_content, bot_name="")

        # 无效输入
        if not parse_result.is_valid:
            self.sender.send_text(chat_id, parse_result.error_hint or "输入格式不正确")
            return

        # 确认在线
        if parse_result.is_at_bot and not parse_result.stock_code and not parse_result.stock_name:
            self.sender.send_text(chat_id, "我在！请输入股票代码或名称，例如：600519 或 00700.HK")
            return

        # 诊股查询
        symbol = parse_result.stock_code or ""
        name = parse_result.stock_name or ""

        if symbol or name:
            self._handle_diagnosis(chat_id, symbol, name)

    def _handle_diagnosis(self, chat_id: str, symbol: str, name: str = "") -> None:
        """处理诊股请求：汇总各模块状态，最后统一发送一条结果消息。"""
        logger.info("处理诊股请求: chat_id={} symbol={}", chat_id, symbol)

        # 执行分析
        result = None
        exception_msg = ""
        try:
            result = self.diagnosis_analyzer.analyze(symbol, name)
        except Exception as e:
            exception_msg = str(e)
            logger.error("诊股分析异常: {}", e)

        # 构建汇总报告
        summary_lines = [f"**{symbol} 诊股分析报告**"]

        if result and result.module_status:
            # 列出每个模块状态
            summary_lines.append("\n**各模块执行状态：**")
            for module, status in result.module_status.items():
                icon = "✅" if status.startswith("成功") else "⚠️"
                summary_lines.append(f"{icon} {module}: {status}")

        # 失败情况
        if not result or result.source == "failed":
            if exception_msg:
                summary_lines.append(f"\n❌ **分析失败**: {exception_msg}")
            if result and result.warnings:
                summary_lines.append(f"\n**失败原因**: {'、'.join(result.warnings)}")

            summary_text = "\n".join(summary_lines)
            self.sender.send_text(chat_id, summary_text)
            logger.info("诊股失败汇总已发送至 chat_id={}", chat_id)
            return

        # 成功情况：继续保存历史并发送卡片
        summary_lines.append(f"\n✅ **分析完成**")
        if result.score > 0:
            summary_lines.append(f"**综合评分**: {result.score}/100")
            summary_lines.append(f"**策略建议**: {result.strategy}")
        if result.summary:
            summary_lines.append(f"**总结**: {result.summary}")
        if result.alert_triggered and result.alert_msg:
            summary_lines.append(f"\n🚨 **持仓警示**: {result.alert_msg}")

        summary_text = "\n".join(summary_lines)
        self.sender.send_text(chat_id, summary_text)

        # 保存诊断历史
        try:
            DiagnosisHistory.create(
                symbol=result.symbol,
                name=result.name,
                current_price=result.support,
                change_pct=0,
                analysis_text=result.analysis_text,
                strategy=result.strategy,
                score=result.score,
                llm_model="claude",
            )
        except Exception as e:
            logger.warning("保存诊断历史失败: {}", e)

        # 发送卡片
        card = self.diagnosis_card_builder.build(result)
        self.sender.send_card(chat_id, card)
        logger.info("诊股卡片已发送至 chat_id={}", chat_id)

    def pre_fetch_report_data(self) -> None:
        """07:30 预拉取晨报所需数据：全球市场 + 持仓新闻，保存到 JSON。"""
        logger.info("开始执行晨报数据预准备...")
        today = date.today().strftime("%Y-%m-%d")

        # 1. 获取全球市场数据
        market_data = {}
        try:
            market = self.data_fetcher.get_global_market()
            if market and getattr(market, "source", "") != "failed":
                market_data = {
                    "dow_jones": market.dow_jones,
                    "sp500": market.sp500,
                    "nasdaq": market.nasdaq,
                    "hsi_futures": market.hsi_futures,
                    "usdx": market.usdx,
                    "usdcnh": market.usdcnh,
                    "us_10y": market.us_10y,
                    "source": market.source,
                }
                logger.info("全球市场数据获取成功")
            else:
                logger.warning("全球市场数据获取失败")
        except Exception as e:
            logger.error("获取全球市场数据异常: {}", e)

        # 2. 获取持仓个股新闻
        holdings_news = {}
        portfolio = PortfolioParser().parse()
        news_ok = 0
        news_fail = 0
        for holding in portfolio.holdings:
            try:
                news = self.data_fetcher.get_news(holding.symbol)
                if news:
                    holdings_news[holding.symbol] = news
                    news_ok += 1
                else:
                    news_fail += 1
            except Exception as e:
                logger.debug("获取 {} 新闻失败: {}", holding.symbol, e)
                news_fail += 1
        logger.info("持仓新闻获取完成: 成功 {} 只, 失败 {} 只", news_ok, news_fail)

        # 3. 读取 portfolio.md 原始内容
        portfolio_raw = ""
        try:
            portfolio_path = Path("portfolio.md")
            if portfolio_path.exists():
                portfolio_raw = portfolio_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("读取 portfolio.md 失败: {}", e)

        # 4. 组装 input_data
        input_data = {
            "date_str": today,
            "fetch_time": "07:30",
            "market_snapshot": market_data,
            "holdings_news": holdings_news,
            "portfolio": {
                "holdings": [
                    {
                        "symbol": h.symbol,
                        "name": h.name,
                        "cost_price": h.cost_price,
                        "quantity": h.quantity,
                        "sector": h.sector,
                        "notes": h.notes,
                    }
                    for h in portfolio.holdings
                ],
                "watch_sectors": portfolio.watch_sectors,
                "alerts": portfolio.alerts,
                "raw_md": portfolio_raw,
            },
        }

        # 5. 保存到 data/cache/report_input/{date}.json
        cache_dir = Path("data/cache/report_input")
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path = cache_dir / f"{today}.json"
            cache_path.write_text(
                json.dumps(input_data, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            logger.info("晨报输入数据已保存到 {}", cache_path)
        except Exception as e:
            logger.error("保存晨报输入数据失败: {}", e)

        # 6. 飞书通知
        chat_id = getattr(self.settings.feishu, "default_chat_id", "")
        if chat_id:
            lines = ["**📊 晨报数据预准备完成**"]
            lines.append(f"- 日期: {today}")
            lines.append(f"- 全球市场: {'✅ 成功' if market_data else '⚠️ 失败'}")
            lines.append(f"- 持仓新闻: {news_ok}/{len(portfolio.holdings)} 成功")
            if news_fail > 0:
                lines.append(f"- 新闻失败: {news_fail} 只")
            self.sender.send_text(chat_id, "\n".join(lines))

    def generate_kimi_report(self) -> None:
        """07:35 调用 Kimi Agent 生成晨报 Markdown。"""
        logger.info("开始执行 Kimi 晨报生成...")
        today = date.today().strftime("%Y-%m-%d")

        # 1. 读取预准备的数据
        input_path = Path(f"data/cache/report_input/{today}.json")
        if not input_path.exists():
            logger.error("晨报输入数据不存在: {}", input_path)
            chat_id = getattr(self.settings.feishu, "default_chat_id", "")
            if chat_id:
                self.sender.send_text(chat_id, "⚠️ Kimi 晨报生成失败：预准备数据不存在")
            return

        try:
            input_data = json.loads(input_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error("读取晨报输入数据失败: {}", e)
            return

        # 2. 检查 Kimi Browser 是否可用
        if not self.kimi_browser:
            logger.error("KimiAgentBrowser 未初始化，无法生成晨报")
            chat_id = getattr(self.settings.feishu, "default_chat_id", "")
            if chat_id:
                self.sender.send_text(
                    chat_id,
                    "⚠️ Kimi 晨报生成失败：浏览器未初始化，启用备用方案"
                )
            return

        # 3. 调用 Kimi Agent 生成晨报
        result = None
        try:
            result = asyncio.run(self.kimi_browser.generate_report(input_data))
        except Exception as e:
            logger.error("Kimi Agent 生成晨报异常: {}", e)

        # 4. 处理结果
        chat_id = getattr(self.settings.feishu, "default_chat_id", "")

        if not result or not result.get("success"):
            error_msg = result.get("error", "未知错误") if result else "调用失败"
            logger.error("Kimi 晨报生成失败: {}", error_msg)

            # 保存失败记录到 KimiRawData
            try:
                KimiRawData.create(
                    data_date=today,
                    task_type="report",
                    content="",
                    status="failed",
                    error_msg=error_msg,
                    elapsed_sec=result.get("elapsed_sec") if result else None,
                )
            except Exception as e:
                logger.warning("保存 Kimi 失败记录失败: {}", e)

            if chat_id:
                self.sender.send_text(
                    chat_id,
                    f"⚠️ Kimi 晨报生成失败：{error_msg}，启用备用方案"
                )
            return

        # 5. 使用 KimiAdapter 清洗和校验
        raw_markdown = result.get("markdown", "")
        adapter_result = KimiAdapter.process(raw_markdown)

        if not adapter_result.get("valid"):
            logger.error("Kimi 返回内容校验失败: {}", adapter_result.get("error"))
            try:
                KimiRawData.create(
                    data_date=today,
                    task_type="report",
                    content=raw_markdown[:5000],
                    status="failed",
                    error_msg=adapter_result.get("error", "校验失败"),
                    elapsed_sec=result.get("elapsed_sec"),
                )
            except Exception as e:
                logger.warning("保存 Kimi 校验失败记录失败: {}", e)

            if chat_id:
                self.sender.send_text(
                    chat_id,
                    f"⚠️ Kimi 晨报校验失败：{adapter_result.get('error')}，启用备用方案"
                )
            return

        cleaned_markdown = adapter_result.get("cleaned", raw_markdown)
        sentiment = adapter_result.get("sentiment", {})

        # 6. 保存到 data/cache/kimi_report/{date}.md
        report_dir = Path("data/cache/kimi_report")
        try:
            report_dir.mkdir(parents=True, exist_ok=True)
            report_path = report_dir / f"{today}.md"
            report_path.write_text(cleaned_markdown, encoding="utf-8")
            logger.info("Kimi 晨报已保存到 {}", report_path)
        except Exception as e:
            logger.error("保存 Kimi 晨报失败: {}", e)

        # 7. 保存原始数据到 KimiRawData 表
        try:
            KimiRawData.create(
                data_date=today,
                task_type="report",
                content=raw_markdown[:10000],
                status="success",
                elapsed_sec=result.get("elapsed_sec"),
                sentiment_mood=sentiment.get("mood"),
                sentiment_score=sentiment.get("score"),
            )
            logger.info("Kimi 原始数据已保存到数据库")
        except Exception as e:
            logger.warning("保存 Kimi 原始数据失败: {}", e)

        # 8. 飞书通知
        if chat_id:
            mood = sentiment.get("mood", "未知")
            score = sentiment.get("score")
            lines = ["**✅ Kimi 晨报生成完成**"]
            lines.append(f"- 日期: {today}")
            lines.append(f"- 情绪: {mood}")
            if score is not None:
                lines.append(f"- 得分: {score}/100")
            lines.append(f"- 耗时: {result.get('elapsed_sec', 0):.1f}秒")
            lines.append(f"- 长度: {len(cleaned_markdown)} 字符")
            self.sender.send_text(chat_id, "\n".join(lines))

    def send_morning_report(self, chat_id: str = "") -> None:
        """生成并发送晨报，优先使用 Kimi 生成的缓存，否则降级到本地生成。"""
        if not chat_id:
            chat_id = getattr(self.settings.feishu, "default_chat_id", "")

        logger.info("开始生成并发送晨报到 chat_id={}", chat_id)
        today = date.today().strftime("%Y-%m-%d")

        # 1. 优先读取 Kimi 生成的晨报缓存
        kimi_report_path = Path(f"data/cache/kimi_report/{today}.md")
        report = None

        if kimi_report_path.exists():
            logger.info("检测到 Kimi 晨报缓存，直接使用")
            try:
                content = kimi_report_path.read_text(encoding="utf-8")
                # 尝试提取情绪信息
                sentiment = KimiAdapter().extract_sentiment(content)
                report = MorningReport(
                    date=today,
                    content=content,
                    source="kimi",
                    module_status={"Kimi 缓存": "成功"},
                )
                # 附加情绪数据到 report 对象（供卡片渲染使用）
                if sentiment.get("mood"):
                    report.sentiment = {
                        "mood": sentiment.get("mood"),
                        "score": sentiment.get("score"),
                    }
                logger.info("Kimi 晨报缓存加载成功，长度={}", len(content))
            except Exception as e:
                logger.error("读取 Kimi 晨报缓存失败: {}", e)
                report = None

        # 2. 如果没有 Kimi 缓存，调用本地生成器
        if not report:
            logger.info("未检测到 Kimi 晨报缓存，调用本地生成器")
            report = self.morning_report_generator.generate()

        # 3. 汇总模块状态
        if report.module_status:
            status_lines = ["**晨报生成模块状态：**"]
            for module, status in report.module_status.items():
                icon = "✅" if status.startswith("成功") else "⚠️"
                status_lines.append(f"{icon} {module}: {status}")
            self.sender.send_text(chat_id, "\n".join(status_lines))

        # 4. 保存晨报记录（包含情绪数据）
        try:
            sentiment_mood = None
            sentiment_score = None
            if hasattr(report, "sentiment") and isinstance(report.sentiment, dict):
                sentiment_mood = report.sentiment.get("mood")
                sentiment_score = report.sentiment.get("score")

            MorningReportRecord.create(
                report_date=report.date,
                content=report.content,
                source=report.source,
                chat_id=chat_id,
                warnings="\n".join(report.warnings),
                kimi_source="cache" if report.source == "kimi" else "",
                sentiment_mood=sentiment_mood,
                sentiment_score=sentiment_score,
            )
        except Exception as e:
            logger.warning("保存晨报记录失败: {}", e)

        # 5. 构建并发送卡片
        if report.source == "failed":
            self.sender.send_text(
                chat_id,
                f"晨报生成失败：{'、'.join(report.warnings)}"
            )
            return

        card = self.morning_report_card_builder.build(report)
        self.sender.send_card(chat_id, card)
        logger.info("晨报卡片已发送至 chat_id={}", chat_id)

    def send_delay_warning(self, chat_id: str, data_time: str) -> None:
        """发送晨报延迟警告。"""
        card = self.morning_report_card_builder.build_delay_warning(data_time)
        self.sender.send_card(chat_id, card)

    def pre_fetch_data(self) -> None:
        """每晚 19:00 预拉取持仓数据到本地缓存，force_refresh 强制刷新。"""
        logger.info("开始执行数据预拉取...")
        portfolio = PortfolioParser().parse()
        total = len(portfolio.holdings)
        quote_ok = 0
        quote_fail = []
        news_ok = 0
        news_fail = []

        for holding in portfolio.holdings:
            # 行情（force_refresh 强制刷新缓存）
            try:
                quote = self.data_fetcher.get_stock_quote(
                    holding.symbol, force_refresh=True
                )
                if quote.source != "failed":
                    quote_ok += 1
                else:
                    quote_fail.append(holding.symbol)
            except Exception as e:
                logger.debug("预拉取 {} 行情失败: {}", holding.symbol, e)
                quote_fail.append(holding.symbol)

            # 新闻（force_refresh 强制刷新缓存）
            try:
                news = self.data_fetcher.get_news(holding.symbol, force_refresh=True)
                if news:
                    news_ok += 1
                else:
                    news_fail.append(holding.symbol)
            except Exception as e:
                logger.debug("预拉取 {} 新闻失败: {}", holding.symbol, e)
                news_fail.append(holding.symbol)

        # 全球市场数据
        market_ok = False
        try:
            market = self.data_fetcher.get_global_market(force_refresh=True)
            market_ok = market.source != "failed"
        except Exception as e:
            logger.debug("预拉取全球市场数据失败: {}", e)

        # 清理 7 天前过期缓存
        try:
            cleaned = self.data_fetcher.cache.clean_expired(keep_days=7)
        except Exception as e:
            logger.debug("清理过期缓存失败: {}", e)
            cleaned = 0

        logger.info(
            "数据预拉取完成: 行情 {}/{}, 新闻 {}/{}, 全球市场 {}",
            quote_ok, total, news_ok, total, "成功" if market_ok else "失败"
        )

        # 发送汇总通知到飞书
        chat_id = getattr(self.settings.feishu, "default_chat_id", "")
        if chat_id:
            lines = ["**📊 晚间数据预拉取完成**"]
            lines.append(f"- 持仓行情: {quote_ok}/{total} 成功")
            if quote_fail:
                lines.append(f"- 行情失败: {', '.join(quote_fail)}")
            lines.append(f"- 持仓新闻: {news_ok}/{total} 成功")
            if news_fail:
                lines.append(f"- 新闻失败: {', '.join(news_fail)}")
            lines.append(f"- 全球市场: {'✅ 成功' if market_ok else '⚠️ 失败'}")
            if cleaned:
                lines.append(f"- 清理过期缓存: {cleaned} 个文件")
            self.sender.send_text(chat_id, "\n".join(lines))
