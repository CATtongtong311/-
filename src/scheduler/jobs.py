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
        morning_report_func,
        chat_id: str = "",
        hour: int = 8,
        minute: int = 30,
    ):
        """
        Args:
            morning_report_func: 生成并发送晨报的可调用对象
            chat_id: 目标飞书群聊 ID
            hour: 每日触发小时
            minute: 每日触发分钟
        """
        self.morning_report_func = morning_report_func
        self.chat_id = chat_id
        self.hour = hour
        self.minute = minute
        self.scheduler = BackgroundScheduler()

    def start(self) -> None:
        """启动调度器。"""
        # 每日晨报任务
        self.scheduler.add_job(
            self._run_morning_report,
            trigger=CronTrigger(hour=self.hour, minute=self.minute),
            id="morning_report",
            replace_existing=True,
        )
        logger.info("已注册每日晨报任务: {:02d}:{:02d}", self.hour, self.minute)

        # 每日清理 7 天前的晨报记录
        self.scheduler.add_job(
            self._cleanup_old_reports,
            trigger=CronTrigger(hour=3, minute=0),  # 凌晨 3 点执行清理
            id="cleanup_reports",
            replace_existing=True,
        )
        logger.info("已注册晨报清理任务: 03:00")

        self.scheduler.start()
        logger.info("调度器已启动")

    def stop(self) -> None:
        """停止调度器。"""
        self.scheduler.shutdown(wait=False)
        logger.info("调度器已停止")

    def _run_morning_report(self):
        """执行晨报生成和推送。"""
        logger.info("开始执行每日晨报任务...")
        try:
            self.morning_report_func(chat_id=self.chat_id)
        except Exception as e:
            logger.error("晨报任务执行失败: {}", e)

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
        """立即触发一次晨报任务（用于测试）。"""
        logger.info("手动触发晨报任务")
        self._run_morning_report()

    def is_running(self) -> bool:
        """检查调度器是否正在运行。"""
        return self.scheduler.running
