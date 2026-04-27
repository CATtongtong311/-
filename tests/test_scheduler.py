import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.scheduler.jobs import SchedulerManager


class TestSchedulerManager:
    def test_start_stop(self):
        mock_func = MagicMock()
        mgr = SchedulerManager(morning_report_func=mock_func, chat_id="chat_123")

        mgr.start()
        assert mgr.is_running() is True

        mgr.stop()
        assert mgr.is_running() is False

    def test_trigger_now(self):
        mock_func = MagicMock()
        mgr = SchedulerManager(morning_report_func=mock_func, chat_id="chat_123")

        mgr.start()
        mgr.trigger_now()
        # 给调度器一点时间执行
        import time
        time.sleep(0.2)
        mock_func.assert_called_once_with(chat_id="chat_123")
        mgr.stop()

    def test_cleanup_old_reports(self):
        from src.core.database import init_db
        from src.core.models import MorningReportRecord

        # 确保表存在
        init_db()

        # 清理已有的测试数据
        MorningReportRecord.delete().execute()

        # 插入 8 天前的记录
        old_date = date.today() - timedelta(days=8)
        MorningReportRecord.create(
            report_date=old_date,
            content="旧晨报",
            source="kimi",
            chat_id="chat_123",
        )
        # 插入 3 天前的记录
        recent_date = date.today() - timedelta(days=3)
        MorningReportRecord.create(
            report_date=recent_date,
            content="新晨报",
            source="kimi",
            chat_id="chat_123",
        )

        assert MorningReportRecord.select().count() == 2

        mock_func = MagicMock()
        mgr = SchedulerManager(morning_report_func=mock_func)
        mgr._cleanup_old_reports()

        # 应该只剩 1 条（3 天前的）
        remaining = MorningReportRecord.select().count()
        assert remaining == 1

        # 清理测试数据
        MorningReportRecord.delete().execute()

    def test_custom_schedule_time(self):
        mock_func = MagicMock()
        mgr = SchedulerManager(
            morning_report_func=mock_func,
            chat_id="chat_123",
            hour=9,
            minute=15,
        )
        assert mgr.hour == 9
        assert mgr.minute == 15
