"""Claude Code CLI 客户端封装。

调用本地 `claude -p` 命令，利用 Claude Code CLI 的分析能力替代 Kimi HTTP API。
要求环境：
    - claude CLI 已安装且可执行
    - ANTHROPIC_AUTH_TOKEN / ANTHROPIC_BASE_URL 已配置（或 .env 中配置了 ANTHROPIC_API_KEY）
"""

import json
import os
import re
import subprocess
from typing import Iterator

from loguru import logger


class ClaudeCodeClient:
    """通过子进程调用 claude -p 进行文本生成。"""

    TIMEOUT = 120  # 默认超时，可通过 chat 参数覆盖

    def __init__(self, api_key: str = "", base_url: str = ""):
        """
        Args:
            api_key: Anthropic/Kimi API Key（留空则读取环境变量）
            base_url: 自定义 API Base URL（留空则读取环境变量）
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY", "")
        self.base_url = base_url or os.environ.get("ANTHROPIC_BASE_URL", "")
        self._claude_cmd = self._find_claude()

    @staticmethod
    def _find_claude() -> str:
        """查找 claude 可执行文件路径。"""
        candidates = [
            os.path.expanduser("~/.local/bin/claude"),
            os.path.expanduser("~/.cargo/bin/claude"),
            "/usr/local/bin/claude",
            "/usr/bin/claude",
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c

        for cmd in ("claude", "claude.exe"):
            for path_dir in os.environ.get("PATH", "").split(os.pathsep):
                full = os.path.join(path_dir.strip('"'), cmd)
                if os.path.isfile(full):
                    return full

        return "claude"

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 4096,
        stream: bool = False,
        timeout: int | None = None,
    ) -> str:
        """发送对话请求，返回生成的文本。

        Args:
            timeout: 自定义超时秒数，None 则使用默认 TIMEOUT
        """
        prompt = self._build_prompt(messages)
        timeout_sec = timeout or self.TIMEOUT

        try:
            result = self._run_claude(prompt, max_tokens, timeout_sec)
            return result
        except subprocess.TimeoutExpired:
            logger.error("Claude Code 请求超时 ({}s)", timeout_sec)
            return ""
        except Exception as e:
            logger.error("Claude Code 调用异常: {}", e)
            return ""

    def chat_stream(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> Iterator[str]:
        """流式对话 — Claude Code CLI 不支持流式，退化为一次性返回。"""
        text = self.chat(messages, temperature, max_tokens, stream=False)
        yield text

    def quick_ask(self, prompt: str, system: str = "") -> str:
        """快速单轮对话。"""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages)

    def _build_prompt(self, messages: list[dict]) -> str:
        """将 messages 列表拼接为单个 prompt 字符串。"""
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                parts.append(f"[系统指令]\n{content}\n")
            elif role == "user":
                parts.append(f"[用户提问]\n{content}\n")
            elif role == "assistant":
                parts.append(f"[助手回复]\n{content}\n")
        return "\n".join(parts)

    def _run_claude(self, prompt: str, max_tokens: int, timeout: int) -> str:
        """执行 claude -p 并返回结果。"""
        env = os.environ.copy()
        if self.api_key:
            env["ANTHROPIC_API_KEY"] = self.api_key
        if self.base_url:
            env["ANTHROPIC_BASE_URL"] = self.base_url

        cmd = [
            self._claude_cmd,
            "-p",
            "--dangerously-skip-permissions",
            "--bare",
            "--output-format", "text",
            prompt,
        ]

        logger.debug("Claude Code CLI 调用: {} (timeout={}s)", self._claude_cmd, timeout)

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
            cwd=os.getcwd(),
            stdin=subprocess.DEVNULL,
        )

        if proc.returncode != 0:
            stderr = proc.stderr.strip()
            if stderr:
                logger.warning("Claude Code stderr: {}", stderr[:500])
            if not proc.stdout.strip():
                raise RuntimeError(f"Claude Code 退出码 {proc.returncode}: {stderr[:500]}")

        output = proc.stdout.strip()
        return output

    @staticmethod
    def extract_json(text: str) -> dict:
        """从文本中提取第一个 JSON 对象。"""
        text = text.strip()
        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 查找 ```json ... ``` 代码块
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 查找第一个 { ... }
        m = re.search(r"(\{[\s\S]*\})", text)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except json.JSONDecodeError:
                pass

        return {}
