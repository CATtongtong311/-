"""飞书卡片发送器：构建卡片、注入免责声明、发送消息。"""

import json

from loguru import logger

from src.feishu.disclaimer import inject_footer


def build_card_payload(title: str, color: str = "blue", elements: list | None = None) -> dict:
    """构建飞书 Card JSON 2.0 结构。"""
    return {
        "schema": "2.0",
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "template": color,
        },
        "body": {
            "elements": elements or [],
        },
    }


class CardSender:
    """通过飞书 HTTP API 发送消息卡片和纯文本。"""

    def __init__(self, app_id: str = "", app_secret: str = ""):
        self.app_id = app_id
        self.app_secret = app_secret
        # lark-oapi HTTP client 延迟初始化
        self._client = None

    def _get_client(self):
        """懒加载 lark-oapi HTTP client。"""
        if self._client is None:
            try:
                from lark_oapi import AppType, Client

                self._client = Client.builder() \
                    .app_type(AppType.SELF) \
                    .app_id(self.app_id) \
                    .app_secret(self.app_secret) \
                    .build()
            except ImportError as e:
                logger.error("lark-oapi 未安装: {}", e)
                raise
        return self._client

    def send_card(self, chat_id: str, card_dict: dict) -> dict:
        """发送卡片消息，自动注入免责声明和大小预检。"""
        card_with_footer = inject_footer(card_dict)

        size_kb = len(json.dumps(card_with_footer).encode("utf-8")) / 1024
        if size_kb > 25:
            logger.warning("卡片大小 {:.1f}KB 超过 25KB 阈值，可能发送失败", size_kb)

        try:
            from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

            client = self._get_client()
            req = CreateMessageRequest.builder() \
                .receive_id_type("chat_id") \
                .request_body(CreateMessageRequestBody.builder()
                      .receive_id(chat_id)
                      .msg_type("interactive")
                      .content(json.dumps(card_with_footer))
                      .build()) \
                .build()
            resp = client.im.v1.message.create(req)
            return {"code": resp.code, "msg": resp.msg, "data": resp.data}
        except Exception as e:
            logger.error("发送卡片失败: {}", e)
            return {"code": -1, "msg": str(e), "data": None}

    def send_text(self, chat_id: str, text: str) -> dict:
        """发送纯文本消息。"""
        try:
            from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

            client = self._get_client()
            content = json.dumps({"text": text})
            req = CreateMessageRequest.builder() \
                .receive_id_type("chat_id") \
                .request_body(CreateMessageRequestBody.builder()
                      .receive_id(chat_id)
                      .msg_type("text")
                      .content(content)
                      .build()) \
                .build()
            resp = client.im.v1.message.create(req)
            return {"code": resp.code, "msg": resp.msg, "data": resp.data}
        except Exception as e:
            logger.error("发送文本失败: {}", e)
            return {"code": -1, "msg": str(e), "data": None}
