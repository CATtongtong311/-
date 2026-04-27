import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import math
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from src.data.quota import QuotaManager
from src.data.validator import DataValidator, ValidationResult


class TestQuotaManager:
    def setup_method(self):
        self.quota = QuotaManager(daily_limit=100)

    def teardown_method(self):
        # 清理测试数据
        from src.core.models import ApiCallLog
        ApiCallLog.delete().where(ApiCallLog.source == "tushare").execute()

    def test_initial_remaining(self):
        assert self.quota.remaining() == 100

    def test_record_consumes_quota(self):
        self.quota.record("daily", success=True)
        self.quota.record("daily", success=True)
        assert self.quota.remaining() == 98

    def test_record_failure_increases_error(self):
        self.quota.record("daily", success=False)
        self.quota.record("daily", success=False)
        # remaining 应该是 98（2 次调用都计入了 call_count）
        assert self.quota.remaining() == 98

    def test_should_fallback_low_remaining(self):
        # 模拟剩余额度 < 20
        with patch.object(self.quota, "remaining", return_value=10):
            assert self.quota.should_fallback() is True

    def test_should_fallback_high_error_rate(self):
        # 记录 10 次成功 + 20 次失败 = 30 次调用，错误率 66%
        for _ in range(10):
            self.quota.record("daily", success=True)
        for _ in range(20):
            self.quota.record("daily", success=False)
        assert self.quota.should_fallback() is True

    def test_should_fallback_normal(self):
        # 记录 10 次成功，剩余 90，错误率 0%
        for _ in range(10):
            self.quota.record("daily", success=True)
        assert self.quota.should_fallback() is False
        assert self.quota.remaining() == 90

    def test_check_when_remaining_zero(self):
        with patch.object(self.quota, "remaining", return_value=0):
            assert self.quota.check("daily") is False

    def test_check_when_remaining_positive(self):
        with patch.object(self.quota, "remaining", return_value=5):
            assert self.quota.check("daily") is True


class TestDataValidator:
    def setup_method(self):
        self.validator = DataValidator()

    def test_valid_quote(self):
        data = {
            "open": 100.0,
            "high": 105.0,
            "low": 99.0,
            "close": 102.0,
            "volume": 10000,
            "change_pct": 2.0,
        }
        result = self.validator.validate_quote(data)
        assert result.is_valid is True
        assert result.is_suspended is False
        assert result.has_null is False
        assert result.is_abnormal_price is False
        assert result.fallback_needed is False
        assert result.warnings == []

    def test_suspended_volume_zero(self):
        data = {
            "open": 100.0,
            "high": 100.0,
            "low": 100.0,
            "close": 100.0,
            "volume": 0,
            "change_pct": 0.0,
        }
        result = self.validator.validate_quote(data)
        assert result.is_suspended is True
        assert result.fallback_needed is True
        assert "成交量为 0" in result.warnings[0]

    def test_suspended_volume_none(self):
        data = {
            "open": 100.0,
            "high": 100.0,
            "low": 100.0,
            "close": 100.0,
            "volume": None,
            "change_pct": 0.0,
        }
        result = self.validator.validate_quote(data)
        assert result.is_suspended is True
        assert result.fallback_needed is True

    def test_null_fields(self):
        data = {
            "open": 100.0,
            "high": None,
            "low": 99.0,
            "close": 102.0,
            "volume": 10000,
            "change_pct": 2.0,
        }
        result = self.validator.validate_quote(data)
        assert result.has_null is True
        assert result.fallback_needed is True
        assert any("high 字段为空值" in w for w in result.warnings)

    def test_nan_fields(self):
        data = {
            "open": 100.0,
            "high": float("nan"),
            "low": 99.0,
            "close": 102.0,
            "volume": 10000,
            "change_pct": 2.0,
        }
        result = self.validator.validate_quote(data)
        assert result.has_null is True
        assert result.fallback_needed is True

    def test_abnormal_price(self):
        data = {
            "open": 100.0,
            "high": 130.0,
            "low": 99.0,
            "close": 125.0,
            "volume": 10000,
            "change_pct": 25.0,
        }
        result = self.validator.validate_quote(data)
        assert result.is_abnormal_price is True
        assert result.fallback_needed is False  # 异常价格不触发降级
        assert "涨跌幅异常" in result.warnings[0]

    def test_empty_data(self):
        result = self.validator.validate_quote({})
        assert result.is_valid is False
        assert result.fallback_needed is True
        assert "返回数据为空" in result.warnings[0]

    def test_market_data_valid(self):
        data = {"dow_jones": {"close": 35000}, "sp500": {"close": 4500}}
        result = self.validator.validate_market_data(data)
        assert result.is_valid is True
        assert result.fallback_needed is False

    def test_market_data_empty(self):
        result = self.validator.validate_market_data({})
        assert result.is_valid is False
        assert result.fallback_needed is True

    def test_market_data_all_none(self):
        result = self.validator.validate_market_data({"dow_jones": None, "sp500": None})
        assert result.is_valid is False
        assert result.fallback_needed is True
