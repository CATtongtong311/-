import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import json
from unittest.mock import MagicMock, patch

import pytest

from src.feishu.card_sender import CardSender, build_card_payload
from src.feishu.disclaimer import DISCLAIMER_TEXT, inject_footer
from src.feishu.gateway import FeishuGateway, create_gateway


class TestBuildCardPayload:
    def test_default_structure(self):
        payload = build_card_payload("测试标题")
        assert payload["schema"] == "2.0"
        assert payload["header"]["title"]["content"] == "测试标题"
        assert payload["header"]["template"] == "blue"
        assert payload["body"]["elements"] == []

    def test_with_elements(self):
        elements = [{"tag": "div", "text": {"tag": "plain_text", "content": "内容"}}]
        payload = build_card_payload("标题", color="red", elements=elements)
        assert payload["header"]["template"] == "red"
        assert payload["body"]["elements"] == elements


class TestInjectFooter:
    def test_injects_disclaimer_and_time(self):
        card = build_card_payload("标题")
        result = inject_footer(card, data_time="14:30")

        assert result["body"]["elements"][0]["text"]["content"] == "**数据截止 14:30**"
        assert DISCLAIMER_TEXT in result["body"]["elements"][1]["text"]["content"]

    def test_does_not_mutate_original(self):
        card = build_card_payload("标题")
        original_len = len(card["body"]["elements"])
        inject_footer(card, data_time="09:00")
        assert len(card["body"]["elements"]) == original_len

    def test_uses_current_time_when_none(self):
        card = build_card_payload("标题")
        result = inject_footer(card)
        # 验证格式为 HH:MM
        content = result["body"]["elements"][0]["text"]["content"]
        assert content.startswith("**数据截止 ")
        assert "**" in content


class TestCardSenderSizeCheck:
    def test_size_warning_over_25kb(self):
        sender = CardSender("fake_id", "fake_secret")
        # 构造一个超过 25KB 的卡片
        big_elements = [
            {"tag": "div", "text": {"tag": "plain_text", "content": "x" * 30000}}
        ]
        card = build_card_payload("大卡片", elements=big_elements)

        with patch("src.feishu.card_sender.logger") as mock_logger:
            # mock lark-oapi 客户端，避免真实网络调用
            with patch.object(sender, "_get_client") as mock_get_client:
                mock_client = MagicMock()
                mock_resp = MagicMock()
                mock_resp.code = 0
                mock_resp.msg = "ok"
                mock_resp.data = None
                mock_client.im.v1.message.create.return_value = mock_resp
                mock_get_client.return_value = mock_client

                sender.send_card("chat_123", card)

        mock_logger.warning.assert_called_once()
        assert "超过 25KB" in mock_logger.warning.call_args[0][0]

    def test_no_warning_under_25kb(self):
        sender = CardSender("fake_id", "fake_secret")
        card = build_card_payload("小卡片")

        with patch("src.feishu.card_sender.logger") as mock_logger:
            with patch.object(sender, "_get_client") as mock_get_client:
                mock_client = MagicMock()
                mock_resp = MagicMock()
                mock_resp.code = 0
                mock_resp.msg = "ok"
                mock_resp.data = None
                mock_client.im.v1.message.create.return_value = mock_resp
                mock_get_client.return_value = mock_client

                sender.send_card("chat_123", card)

        mock_logger.warning.assert_not_called()


class TestFeishuGatewayInit:
    def test_init_params(self):
        gw = FeishuGateway(
            app_id="test_id",
            app_secret="test_secret",
            encrypt_key="enc_key",
            verification_token="ver_token",
        )
        assert gw.app_id == "test_id"
        assert gw.app_secret == "test_secret"
        assert gw.encrypt_key == "enc_key"
        assert gw.verification_token == "ver_token"
        assert gw.is_running() is False

    def test_create_gateway_factory(self):
        gw = create_gateway(
            app_id="id",
            app_secret="secret",
            on_message=lambda x: x,
        )
        assert isinstance(gw, FeishuGateway)
        assert gw.on_message is not None

    def test_start_stop_lifecycle(self):
        gw = FeishuGateway(app_id="id", app_secret="secret")
        # 由于实际连接需要真实凭据，这里仅验证状态流转
        # start 会立即在后台线程运行，但因为没有真实网络连接，
        # 它会很快失败并进入重连循环；我们在 start 后立即 stop
        with patch.object(gw, "_create_client") as mock_create:
            mock_client = MagicMock()
            mock_client.start.side_effect = Exception("网络不可用")
            mock_create.return_value = mock_client

            gw.start()
            # 给线程一点启动时间
            import time
            time.sleep(0.1)
            assert gw.is_running() is True

            gw.stop()
            assert gw.is_running() is False

    def test_handle_message_extracts_payload(self):
        gw = FeishuGateway(app_id="id", app_secret="secret")
        received = []
        gw.on_message = lambda p: received.append(p)

        # 构造模拟事件
        mock_event = MagicMock()
        mock_event.event.message.chat_id = "chat_abc"
        mock_event.event.message.message_type = "text"
        mock_event.event.message.content = '{"text": "hello"}'
        mock_event.event.message.message_id = "msg_123"
        mock_event.event.sender.sender_id.open_id = "user_open_id"

        gw._handle_message(mock_event)

        assert len(received) == 1
        assert received[0]["chat_id"] == "chat_abc"
        assert received[0]["message_type"] == "text"
        assert received[0]["content"] == '{"text": "hello"}'
        assert received[0]["sender_open_id"] == "user_open_id"

    def test_handle_message_empty_event(self):
        gw = FeishuGateway(app_id="id", app_secret="secret")
        received = []
        gw.on_message = lambda p: received.append(p)

        mock_event = MagicMock()
        mock_event.event = None

        gw._handle_message(mock_event)
        assert len(received) == 0
