"""中央调度器：整合飞书消息、诊股分析、晨报生成和卡片发送。"""

from loguru import logger

from src.analysis.diagnosis import DiagnosisAnalyzer
from src.analysis.morning_report import MorningReportGenerator
from src.cards.diagnosis_card import DiagnosisCardBuilder
from src.cards.morning_report_card import MorningReportCardBuilder
from src.core.models import DiagnosisHistory, MorningReportRecord
from src.data.fetcher import DataFetcher
from src.feishu.card_sender import CardSender
from src.feishu.message_parser import MessageParser
from src.llm.kimi_client import KimiClient
from src.portfolio.parser import PortfolioParser


class BotOrchestrator:
    """机器人物流调度中心：处理用户消息、生成分析、发送卡片。"""

    def __init__(self, settings):
        self.settings = settings

        # 数据层
        self.data_fetcher = DataFetcher(tushare_token=settings.data_source.token)

        # LLM 层
        self.kimi = KimiClient(api_key=settings.llm.kimi_api_key)

        # 分析层
        self.diagnosis_analyzer = DiagnosisAnalyzer(
            data_fetcher=self.data_fetcher,
            kimi_client=self.kimi,
            portfolio_parser=PortfolioParser(),
        )
        self.morning_report_generator = MorningReportGenerator(
            data_fetcher=self.data_fetcher,
            kimi_client=self.kimi,
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
        """处理诊股请求。"""
        logger.info("处理诊股请求: chat_id={} symbol={}", chat_id, symbol)

        result = self.diagnosis_analyzer.analyze(symbol, name)

        # 保存诊断历史
        try:
            DiagnosisHistory.create(
                symbol=result.symbol,
                name=result.name,
                current_price=result.support,  # 用支撑价占位，实际应从 quote 获取
                change_pct=0,
                analysis_text=result.analysis_text,
                strategy=result.strategy,
                score=result.score,
                llm_model="kimi",
            )
        except Exception as e:
            logger.warning("保存诊断历史失败: {}", e)

        # 构建并发送卡片
        if result.source == "failed":
            card = self.diagnosis_card_builder.build_error_card(
                symbol, "\n".join(result.warnings)
            )
        else:
            card = self.diagnosis_card_builder.build(result)

        self.sender.send_card(chat_id, card)
        logger.info("诊股卡片已发送至 chat_id={}", chat_id)

    def send_morning_report(self, chat_id: str = "") -> None:
        """生成并发送晨报。"""
        if not chat_id:
            chat_id = self.settings.feishu.get("default_chat_id", "")

        logger.info("开始生成并发送晨报到 chat_id={}", chat_id)

        report = self.morning_report_generator.generate()

        # 保存晨报记录
        try:
            MorningReportRecord.create(
                report_date=report.date,
                content=report.content,
                source=report.source,
                chat_id=chat_id,
                warnings="\n".join(report.warnings),
            )
        except Exception as e:
            logger.warning("保存晨报记录失败: {}", e)

        # 构建并发送卡片
        card = self.morning_report_card_builder.build(report)
        self.sender.send_card(chat_id, card)
        logger.info("晨报卡片已发送至 chat_id={}", chat_id)

    def send_delay_warning(self, chat_id: str, data_time: str) -> None:
        """发送晨报延迟警告。"""
        card = self.morning_report_card_builder.build_delay_warning(data_time)
        self.sender.send_card(chat_id, card)
