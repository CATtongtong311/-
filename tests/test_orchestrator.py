import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from unittest.mock import MagicMock, patch

import pytest

from src.orchestrator import BotOrchestrator


class MockSettings:
    """模拟配置对象。"""
    class Feishu:
        app_id = "test_id"
        app_secret = "test_secret"
        default_chat_id = "chat_default"
    class DataSource:
        token = "test_token"
    class LLM:
        kimi_api_key = "test_kimi_key"

    feishu = Feishu()
    data_source = DataSource()
    llm = LLM()


class TestBotOrchestrator:
    def setup_method(self):
        self.settings = MockSettings()
        with patch("src.orchestrator.DataFetcher"):
            with patch("src.orchestrator.KimiClient"):
                with patch("src.orchestrator.DiagnosisAnalyzer") as mock_diag:
                    with patch("src.orchestrator.MorningReportGenerator") as mock_mr:
                        with patch("src.orchestrator.CardSender"):
                            self.orch = BotOrchestrator(self.settings)
                            self.mock_diag = mock_diag
                            self.mock_mr = mock_mr

    def test_handle_message_text(self):
        mock_result = MagicMock()
        mock_result.is_valid = True
        mock_result.is_at_bot = True
        mock_result.stock_code = "600519"
        mock_result.stock_name = ""
        mock_result.error_hint = None

        with patch.object(self.orch.message_parser, "parse", return_value=mock_result):
            with patch.object(self.orch, "_handle_diagnosis") as mock_handle:
                self.orch.handle_message({
                    "chat_id": "chat_123",
                    "content": '{"text": "600519"}',
                    "message_type": "text",
                })
                mock_handle.assert_called_once_with("chat_123", "600519", "")

    def test_handle_message_invalid(self):
        mock_result = MagicMock()
        mock_result.is_valid = False
        mock_result.error_hint = "未找到该代码"

        with patch.object(self.orch.message_parser, "parse", return_value=mock_result):
            with patch.object(self.orch.sender, "send_text") as mock_send:
                self.orch.handle_message({
                    "chat_id": "chat_123",
                    "content": '{"text": "invalid"}',
                    "message_type": "text",
                })
                mock_send.assert_called_once_with("chat_123", "未找到该代码")

    def test_handle_message_non_text(self):
        with patch.object(self.orch.sender, "send_text") as mock_send:
            self.orch.handle_message({
                "chat_id": "chat_123",
                "content": "{}",
                "message_type": "image",
            })
            mock_send.assert_not_called()

    def test_handle_message_at_bot_empty(self):
        mock_result = MagicMock()
        mock_result.is_valid = True
        mock_result.is_at_bot = True
        mock_result.stock_code = None
        mock_result.stock_name = None
        mock_result.error_hint = None

        with patch.object(self.orch.message_parser, "parse", return_value=mock_result):
            with patch.object(self.orch.sender, "send_text") as mock_send:
                self.orch.handle_message({
                    "chat_id": "chat_123",
                    "content": '{"text": "@机器人"}',
                    "message_type": "text",
                })
                mock_send.assert_called_once()
                assert "我在" in mock_send.call_args[0][1]

    def test_send_morning_report(self):
        mock_report = MagicMock()
        mock_report.date = "2024-04-26"
        mock_report.content = "晨报内容"
        mock_report.source = "kimi"
        mock_report.warnings = []

        self.orch.morning_report_generator.generate.return_value = mock_report

        with patch("src.orchestrator.MorningReportRecord"):
            with patch.object(self.orch.morning_report_card_builder, "build") as mock_build:
                with patch.object(self.orch.sender, "send_card") as mock_send:
                    mock_build.return_value = {"schema": "2.0"}
                    self.orch.send_morning_report("chat_123")
                    mock_send.assert_called_once()

    def test_send_delay_warning(self):
        with patch.object(self.orch.sender, "send_card") as mock_send:
            self.orch.send_delay_warning("chat_123", "08:25")
            mock_send.assert_called_once()
