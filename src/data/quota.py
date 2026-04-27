"""Tushare 额度监控与自动降级触发。"""

from datetime import date

from loguru import logger

from src.core.models import ApiCallLog


class QuotaManager:
    """管理 Tushare 每日调用额度，触发降级。"""

    def __init__(self, daily_limit: int = 400):
        self.daily_limit = daily_limit

    def _get_or_create_log(self, endpoint: str) -> ApiCallLog:
        """获取或创建今日调用记录。"""
        today = date.today()
        log, created = ApiCallLog.get_or_create(
            source="tushare",
            endpoint=endpoint,
            call_date=today,
            defaults={"call_count": 0, "error_count": 0},
        )
        return log

    def check(self, endpoint: str) -> bool:
        """检查当日是否还可调用指定接口。"""
        return self.remaining() > 0

    def record(self, endpoint: str, success: bool) -> None:
        """记录一次调用结果。"""
        log = self._get_or_create_log(endpoint)
        log.call_count += 1
        if not success:
            log.error_count += 1
        log.save()

        remaining = self.remaining()
        if remaining < 20:
            logger.error("Tushare 额度预警：剩余 {} 次", remaining)
        elif remaining < 50:
            logger.warning("Tushare 额度预警：剩余 {} 次", remaining)

    def remaining(self) -> int:
        """返回当日剩余额度。"""
        today = date.today()
        total_used = (
            ApiCallLog.select(ApiCallLog.call_count)
            .where(ApiCallLog.source == "tushare", ApiCallLog.call_date == today)
            .scalar() or 0
        )
        return max(0, self.daily_limit - total_used)

    def should_fallback(self) -> bool:
        """当剩余额度 < 20 或当日错误率 > 50% 时返回 True。"""
        if self.remaining() < 20:
            return True

        today = date.today()
        logs = ApiCallLog.select().where(
            ApiCallLog.source == "tushare", ApiCallLog.call_date == today
        )
        total_calls = sum(log.call_count for log in logs)
        total_errors = sum(log.error_count for log in logs)

        if total_calls > 0 and (total_errors / total_calls) > 0.5:
            return True

        return False
