"""定时任务调度器：每日晨报推送 + 过期数据清理。"""

from datetime import date, datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from src.core.models import MorningReportRecord


class SchedulerManager:
    """管理 APScheduler 定时任务。"""

    def __init__(
        self,
        morning_report_send_func,
        pre_fetch_report_data_func=None,
        kimi_generate_func=None,
        pre_fetch_func=None,
        chat_id: str = "",
        hour: int = 8,
        minute: int = 0,
    ):
        """
        Args:
            morning_report_send_func: 08:00 读取并发送晨报的可调用对象
            pre_fetch_report_data_func: 07:30 预拉取全球市场+持仓新闻数据的可调用对象（可选）
            kimi_generate_func: 07:35 调用 Kimi Agent 生成晨报的可调用对象（可选）
            pre_fetch_func: 每晚 19:00 预拉取数据的可调用对象（可选）
            chat_id: 目标飞书群聊 ID
            hour: 每日晨报触发小时（默认 8）
            minute: 每日晨报触发分钟（默认 0）
        """
        self.morning_report_send_func = morning_report_send_func
        self.pre_fetch_report_data_func = pre_fetch_report_data_func
        self.kimi_generate_func = kimi_generate_func
        self.pre_fetch_func = pre_fetch_func
        self.chat_id = chat_id
        self.hour = hour
        self.minute = minute
        self.scheduler = BackgroundScheduler()

    def start(self) -> None:
        """启动调度器。"""
        # 07:30 预拉取晨报数据（全球市场 + 持仓新闻）
        if self.pre_fetch_report_data_func:
            self.scheduler.add_job(
                self._run_pre_fetch_report_data,
                trigger=CronTrigger(hour=7, minute=30),
                id="pre_fetch_report_data",
                replace_existing=True,
            )
            logger.info("已注册晨报数据预准备任务: 07:30")

        # 07:35 Kimi Agent 生成晨报（预留 20 分钟生成时间）
        if self.kimi_generate_func:
            self.scheduler.add_job(
                self._run_kimi_generate,
                trigger=CronTrigger(hour=7, minute=35),
                id="kimi_generate",
                replace_existing=True,
            )
            logger.info("已注册 Kimi 晨报生成任务: 07:35")

        # 08:00 晨报发送任务
        self.scheduler.add_job(
            self._run_morning_report_send,
            trigger=CronTrigger(hour=self.hour, minute=self.minute),
            id="morning_report_send",
            replace_existing=True,
        )
        logger.info("已注册每日晨报发送任务: {:02d}:{:02d}", self.hour, self.minute)

        # 每日清理 7 天前的晨报记录
        self.scheduler.add_job(
            self._cleanup_old_reports,
            trigger=CronTrigger(hour=3, minute=0),  # 凌晨 3 点执行清理
            id="cleanup_reports",
            replace_existing=True,
        )
        logger.info("已注册晨报清理任务: 03:00")

        # 每晚 19:00 预拉取数据（缓存到本地，加速次日诊股）
        if self.pre_fetch_func:
            self.scheduler.add_job(
                self._run_pre_fetch,
                trigger=CronTrigger(hour=19, minute=0),
                id="pre_fetch_data",
                replace_existing=True,
            )
            logger.info("已注册数据预拉取任务: 19:00")

        self.scheduler.start()
        logger.info("调度器已启动")

    def stop(self) -> None:
        """停止调度器。"""
        self.scheduler.shutdown(wait=False)
        logger.info("调度器已停止")

    def _run_pre_fetch_report_data(self):
        """执行晨报数据预准备：拉取全球市场 + 持仓新闻，保存到 JSON。"""
        logger.info("开始执行晨报数据预准备任务...")
        try:
            self.pre_fetch_report_data_func()
        except Exception as e:
            logger.error("晨报数据预准备任务执行失败: {}", e)

    def _run_kimi_generate(self):
        """执行 Kimi Agent 晨报生成任务。"""
        logger.info("开始执行 Kimi 晨报生成任务...")
        try:
            self.kimi_generate_func()
        except Exception as e:
            logger.error("Kimi 晨报生成任务执行失败: {}", e)

    def _run_morning_report_send(self):
        """执行晨报读取和推送。"""
        logger.info("开始执行每日晨报发送任务...")
        try:
            self.morning_report_send_func(chat_id=self.chat_id)
        except Exception as e:
            logger.error("晨报发送任务执行失败: {}", e)

    def _run_pre_fetch(self):
        """执行晚间数据预拉取。"""
        logger.info("开始执行晚间数据预拉取任务...")
        try:
            self.pre_fetch_func()
        except Exception as e:
            logger.error("晚间数据预拉取任务执行失败: {}", e)

    def _cleanup_old_reports(self):
        """清理 7 天前的晨报记录。"""
        cutoff = date.today() - timedelta(days=7)
        try:
            deleted = (
                MorningReportRecord.delete()
                .where(MorningReportRecord.report_date < cutoff)
                .execute()
            )
            logger.info("清理 {} 条 7 天前的晨报记录", deleted)
        except Exception as e:
            logger.error("清理晨报记录失败: {}", e)

    def trigger_now(self) -> None:
        """立即触发一次晨报发送任务（用于测试）。"""
        logger.info("手动触发晨报发送任务")
        self._run_morning_report_send()

    def is_running(self) -> bool:
        """检查调度器是否正在运行。"""
        return self.scheduler.running
