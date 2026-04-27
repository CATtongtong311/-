"""飞书消息解析：提取 @机器人、股票代码、中文简称。"""

import re
from dataclasses import dataclass


@dataclass
class ParseResult:
    is_at_bot: bool = False
    raw_text: str = ""
    stock_code: str | None = None
    stock_name: str | None = None
    is_valid: bool = False
    error_hint: str | None = None


class MessageParser:
    """解析飞书消息中的用户意图和股票代码。"""

    # A股: 6位数字
    A_SHARE_PATTERN = re.compile(r"\b\d{6}\b")
    # 港股: 1-5位数字 + .HK（不区分大小写）
    HK_SHARE_PATTERN = re.compile(r"\b\d{1,5}\.HK\b", re.IGNORECASE)
    # 中文简称: 2-6个汉字
    CN_NAME_PATTERN = re.compile(r"[一-龥]{2,6}")
    # @机器人标记
    AT_BOT_PATTERN = re.compile(r"@_user_\d+|@[\w\-]+")

    def parse(self, text: str, bot_name: str = "") -> ParseResult:
        """解析消息文本，返回 ParseResult。"""
        if not text:
            return ParseResult(
                error_hint="请输入股票代码或名称，例如：600519 或 00700.HK",
            )

        # 检查是否 @了机器人
        is_at = bool(self.AT_BOT_PATTERN.search(text))
        if bot_name and bot_name in text:
            is_at = True

        # 去除 @标记，保留纯文本
        raw = self.AT_BOT_PATTERN.sub("", text).strip()
        raw = raw.replace(f"@{bot_name}", "").strip() if bot_name else raw

        if not raw:
            return ParseResult(
                is_at_bot=is_at,
                error_hint="请输入股票代码或名称，例如：600519 或 00700.HK",
            )

        # 提取股票代码
        # 优先匹配港股
        hk_match = self.HK_SHARE_PATTERN.search(raw)
        if hk_match:
            code = hk_match.group(0).upper()
            return ParseResult(
                is_at_bot=is_at,
                raw_text=raw,
                stock_code=code,
                is_valid=True,
            )

        # 匹配A股
        a_match = self.A_SHARE_PATTERN.search(raw)
        if a_match:
            code = a_match.group(0)
            # 简单校验：6位数字，首位为0/3/6
            if code[0] in "036":
                return ParseResult(
                    is_at_bot=is_at,
                    raw_text=raw,
                    stock_code=code,
                    is_valid=True,
                )
            return ParseResult(
                is_at_bot=is_at,
                raw_text=raw,
                stock_code=code,
                is_valid=False,
                error_hint="未找到该代码，请检查是否为 A股/港股 有效代码",
            )

        # 匹配中文简称
        cn_match = self.CN_NAME_PATTERN.search(raw)
        if cn_match:
            return ParseResult(
                is_at_bot=is_at,
                raw_text=raw,
                stock_name=cn_match.group(0),
                is_valid=True,  # 中文简称本期不校验有效性
            )

        # 无任何匹配
        return ParseResult(
            is_at_bot=is_at,
            raw_text=raw,
            is_valid=False,
            error_hint="未找到该代码，请检查是否为 A股/港股 有效代码",
        )
