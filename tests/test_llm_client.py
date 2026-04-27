import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from unittest.mock import MagicMock, patch

import pytest

from src.llm.kimi_client import KimiClient


class TestKimiClient:
    def test_chat_success(self):
        client = KimiClient(api_key="fake_key")
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "  分析结果  "}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }

        with patch.object(client._session, "post", return_value=mock_resp):
            result = client.chat(messages=[{"role": "user", "content": "hello"}])

        assert result == "分析结果"

    def test_chat_empty_response(self):
        client = KimiClient(api_key="fake_key")
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"choices": [{}]}

        with patch.object(client._session, "post", return_value=mock_resp):
            result = client.chat(messages=[{"role": "user", "content": "hello"}])

        assert result == ""

    def test_chat_timeout(self):
        client = KimiClient(api_key="fake_key")

        with patch.object(
            client._session, "post", side_effect=Exception("timeout")
        ):
            result = client.chat(messages=[{"role": "user", "content": "hello"}])

        assert result == ""

    def test_quick_ask(self):
        client = KimiClient(api_key="fake_key")
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "快速回答"}}],
            "usage": {},
        }

        with patch.object(client._session, "post", return_value=mock_resp):
            result = client.quick_ask("问题", system="你是助手")

        assert result == "快速回答"

    def test_model_param(self):
        client = KimiClient(api_key="fake_key", model="moonshot-v1-32k")
        assert client.model == "moonshot-v1-32k"

    def test_chat_stream(self):
        client = KimiClient(api_key="fake_key")
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.iter_lines.return_value = [
            b'data: {"choices": [{"delta": {"content": "Hello"}}]}',
            b'data: {"choices": [{"delta": {"content": " World"}}]}',
            b"data: [DONE]",
        ]

        with patch.object(client._session, "post", return_value=mock_resp):
            chunks = list(client.chat_stream(messages=[{"role": "user", "content": "hi"}]))

        assert "".join(chunks) == "Hello World"
