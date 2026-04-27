"""Kimi (Moonshot) API 客户端封装。"""

import json
from typing import Iterator

import requests
from loguru import logger


class KimiClient:
    """调用 Kimi API 进行对话生成。"""

    BASE_URL = "https://api.moonshot.cn/v1"
    DEFAULT_MODEL = "moonshot-v1-8k"
    TIMEOUT = 60

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.api_key = api_key
        self.model = model
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> str:
        """
        发送对话请求，返回生成的文本。

        Args:
            messages: [{"role": "system"/"user"/"assistant", "content": "..."}]
            temperature: 创造性参数，越低越确定
            max_tokens: 最大生成 token 数
            stream: 是否流式返回
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

        try:
            resp = self._session.post(
                f"{self.BASE_URL}/chat/completions",
                json=payload,
                timeout=self.TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()

            if stream:
                return ""

            choice = data.get("choices", [{}])[0]
            content = choice.get("message", {}).get("content", "")
            usage = data.get("usage", {})
            logger.debug(
                "Kimi 调用完成, prompt_tokens={}, completion_tokens={}",
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
            )
            return content.strip()
        except requests.exceptions.Timeout:
            logger.error("Kimi API 请求超时")
            return ""
        except requests.exceptions.HTTPError as e:
            logger.error("Kimi API HTTP 错误: {}", e.response.text if e.response else e)
            return ""
        except Exception as e:
            logger.error("Kimi API 调用异常: {}", e)
            return ""

    def chat_stream(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> Iterator[str]:
        """流式对话，逐字返回。"""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        try:
            resp = self._session.post(
                f"{self.BASE_URL}/chat/completions",
                json=payload,
                timeout=self.TIMEOUT,
                stream=True,
            )
            resp.raise_for_status()

            for line in resp.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error("Kimi 流式调用异常: {}", e)

    def quick_ask(self, prompt: str, system: str = "") -> str:
        """快速单轮对话。"""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages)
