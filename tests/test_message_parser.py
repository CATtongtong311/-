import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from src.feishu.message_parser import MessageParser, ParseResult


class TestMessageParser:
    def setup_method(self):
        self.parser = MessageParser()

    def test_at_bot_a_share(self):
        result = self.parser.parse("@机器人 600519", bot_name="机器人")
        assert result.is_at_bot is True
        assert result.stock_code == "600519"
        assert result.is_valid is True
        assert result.stock_name is None

    def test_at_bot_hk_share(self):
        result = self.parser.parse("@机器人 00700.HK", bot_name="机器人")
        assert result.is_at_bot is True
        assert result.stock_code == "00700.HK"
        assert result.is_valid is True

    def test_at_bot_hk_share_lowercase(self):
        result = self.parser.parse("@机器人 09988.hk", bot_name="机器人")
        assert result.is_at_bot is True
        assert result.stock_code == "09988.HK"
        assert result.is_valid is True

    def test_at_bot_chinese_name(self):
        result = self.parser.parse("@机器人 茅台", bot_name="机器人")
        assert result.is_at_bot is True
        assert result.stock_name == "茅台"
        assert result.is_valid is True
        assert result.stock_code is None

    def test_at_bot_invalid_code(self):
        result = self.parser.parse("@机器人 999999", bot_name="机器人")
        assert result.is_at_bot is True
        assert result.stock_code == "999999"
        assert result.is_valid is False
        assert "未找到该代码" in (result.error_hint or "")

    def test_at_bot_empty_content(self):
        result = self.parser.parse("@机器人", bot_name="机器人")
        assert result.is_at_bot is True
        assert result.is_valid is False
        assert "请输入股票代码" in (result.error_hint or "")

    def test_no_at_share_code(self):
        result = self.parser.parse("600519")
        assert result.is_at_bot is False
        assert result.stock_code == "600519"
        assert result.is_valid is True

    def test_empty_text(self):
        result = self.parser.parse("")
        assert result.is_valid is False
        assert "请输入股票代码" in (result.error_hint or "")

    def test_multiple_codes_priority_hk(self):
        # 港股优先于 A 股
        result = self.parser.parse("看看 00700.HK 和 600519", bot_name="机器人")
        assert result.stock_code == "00700.HK"

    def test_a_share_prefix_validation(self):
        # 6 开头 = 上海
        assert self.parser.parse("600000").is_valid is True
        # 0 开头 = 深圳
        assert self.parser.parse("000001").is_valid is True
        # 3 开头 = 创业板
        assert self.parser.parse("300750").is_valid is True
        # 9 开头 = 无效
        assert self.parser.parse("999999").is_valid is False

    def test_raw_text_stripped(self):
        result = self.parser.parse("@机器人  600519  看看", bot_name="机器人")
        assert result.raw_text == "600519  看看"
        assert result.stock_code == "600519"
