"""飞书 WebSocket 网关：长连接、事件监听、自动重连。"""

import threading
import time
from typing import Callable

from loguru import logger


class FeishuGateway:
    """基于 lark-oapi WebSocket 的飞书事件网关。"""

    # 指数退避重连参数
    BASE_BACKOFF = 1.0
    MAX_BACKOFF = 60.0
    MAX_RETRIES = 10

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        encrypt_key: str = "",
        verification_token: str = "",
        on_message: Callable | None = None,
    ):
        self.app_id = app_id
        self.app_secret = app_secret
        self.encrypt_key = encrypt_key
        self.verification_token = verification_token
        self.on_message = on_message

        self._client = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._retry_count = 0

    def _build_event_handler(self):
        """构建事件分发处理器。"""
        from lark_oapi.event.dispatcher_handler import EventDispatcherHandler

        builder = EventDispatcherHandler.builder(
            self.encrypt_key, self.verification_token
        )
        builder.register_p2_im_message_receive_v1(self._handle_message)
        return builder.build()

    def _handle_message(self, event):
        """处理 im.message.receive_v1 事件。"""
        try:
            msg = event.event.message if event.event else None
            sender = event.event.sender if event.event else None

            if msg is None:
                logger.warning("收到空消息事件")
                return

            payload = {
                "chat_id": msg.chat_id or "",
                "sender_open_id": (
                    sender.sender_id.open_id if sender and sender.sender_id else ""
                ),
                "message_type": msg.message_type or "",
                "content": msg.content or "",
                "message_id": msg.message_id or "",
            }
            logger.info(
                "收到消息 chat_id={} type={}", payload["chat_id"], payload["message_type"]
            )

            if self.on_message:
                self.on_message(payload)
        except Exception as e:
            logger.error("处理消息事件失败: {}", e)

    def _create_client(self):
        """创建 lark-oapi WebSocket 客户端。"""
        from lark_oapi import ws

        handler = self._build_event_handler()
        return ws.Client(
            app_id=self.app_id,
            app_secret=self.app_secret,
            event_handler=handler,
            auto_reconnect=True,
        )

    def _run_loop(self):
        """在独立线程中运行 WebSocket 连接循环（含指数退避重连）。"""
        self._retry_count = 0
        while self._running and self._retry_count < self.MAX_RETRIES:
            try:
                logger.info(
                    "启动 WebSocket 连接 (重试次数: {}/{})",
                    self._retry_count,
                    self.MAX_RETRIES,
                )
                self._client = self._create_client()
                self._client.start()
                # start() 阻塞直到连接断开；若运行正常退出说明用户调用了 stop
                if not self._running:
                    break
                # 异常断开，进入重连
                self._retry_count += 1
            except Exception as e:
                self._retry_count += 1
                logger.error(
                    "WebSocket 异常 (重试 {}/{}): {}", self._retry_count, self.MAX_RETRIES, e
                )

            if self._running and self._retry_count < self.MAX_RETRIES:
                backoff = min(self.BASE_BACKOFF * (2 ** (self._retry_count - 1)), self.MAX_BACKOFF)
                logger.info("{} 秒后尝试重连...", backoff)
                time.sleep(backoff)

        if self._retry_count >= self.MAX_RETRIES:
            logger.error("WebSocket 重连次数耗尽，停止重连")
        self._running = False
        self._client = None

    def start(self) -> None:
        """启动 WebSocket 连接（非阻塞，在后台线程运行）。"""
        if self._running:
            logger.warning("网关已在运行中")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("飞书网关已启动")

    def stop(self) -> None:
        """优雅关闭 WebSocket 连接。"""
        if not self._running:
            return

        self._running = False
        if self._client is not None:
            try:
                # lark-oapi ws.Client 没有显式 close 方法，
                # 依赖 auto_reconnect=False 或强制结束线程
                pass
            except Exception as e:
                logger.warning("关闭 WebSocket 客户端时出错: {}", e)

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("飞书网关已停止")

    def is_running(self) -> bool:
        """返回网关是否正在运行。"""
        return self._running


def create_gateway(
    app_id: str,
    app_secret: str,
    encrypt_key: str = "",
    verification_token: str = "",
    on_message: Callable | None = None,
) -> FeishuGateway:
    """工厂函数：创建并返回 FeishuGateway 实例。"""
    return FeishuGateway(
        app_id=app_id,
        app_secret=app_secret,
        encrypt_key=encrypt_key,
        verification_token=verification_token,
        on_message=on_message,
    )
