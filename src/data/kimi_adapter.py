"""
Kimi 返回 Markdown 格式校验与清洗模块

负责验证 Kimi Agent 生成的晨报 Markdown 格式，
提取情绪评级、清洗冗余内容、拆分章节。
"""

import re
from typing import Optional


class KimiAdapter:
    """
    Kimi 晨报返回数据的适配器。

    提供以下能力：
    - 验证报告是否包含必需的标题
    - 提取情绪评级和得分
    - 清洗 Markdown 中的冗余内容
    - 提取各章节内容
    """

    # 情绪评级正则：支持 Markdown 加粗 **情绪评级**：乐观/中性/谨慎
    # 也支持纯文本表格格式 情绪评级\t乐观 或 情绪评级 乐观
    _SENTIMENT_RATING_PATTERN = re.compile(
        r"(?:\*\*情绪评级\*\*[:：]|情绪评级)[:：\s]+(乐观|中性|谨慎)",
        re.MULTILINE,
    )

    # 情绪得分正则：支持 Markdown 加粗 **情绪得分**：XX/100
    # 也支持纯文本表格格式 情绪得分\t65/100 或 情绪得分 65/100
    _SENTIMENT_SCORE_PATTERN = re.compile(
        r"(?:\*\*情绪得分\*\*[:：]|情绪得分)[:：\s]+(\d{1,3})\s*/\s*100",
        re.MULTILINE,
    )

    # 章节标题正则：匹配 ## 开头的二级标题
    _SECTION_PATTERN = re.compile(
        r"^##\s+(.*?)$\n(.*?)(?=^##\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )

    # 免责声明起始标记
    _DISCLAIMER_MARKERS = [
        "*免责声明",
        "**免责声明",
        "免责声明",
        "【免责声明】",
        "> 免责声明",
    ]

    @staticmethod
    def validate_report(markdown: str) -> bool:
        """
        验证 Markdown 报告是否包含必需的晨报标题。

        Kimi 有时输出 `# 晨报`，有时直接输出 `晨报`，都予以接受。

        参数:
            markdown: Kimi 返回的 Markdown 字符串

        返回:
            如果包含晨报标题则返回 True，否则返回 False
        """
        if not markdown or not isinstance(markdown, str):
            return False

        # 匹配 `# 晨报` 或 `# 晨报 YYYY-MM-DD` 或 `晨报 YYYY-MM-DD`
        pattern = re.compile(r"(^#\s+晨报|^晨报\s+\d{4}-\d{2}-\d{2})", re.MULTILINE)
        return bool(pattern.search(markdown))

    @classmethod
    def extract_sentiment(cls, markdown: str) -> dict:
        """
        从 Markdown 中提取情绪评级和情绪得分。

        参数:
            markdown: Kimi 返回的 Markdown 字符串

        返回:
            字典，结构如下：
            {
                "rating": "乐观" | "中性" | "谨慎" | None,
                "score": int | None,
                "raw_rating": str | None,   # 原始匹配文本
                "raw_score": str | None,    # 原始匹配文本
            }
        """
        result = {
            "mood": None,
            "score": None,
            "raw_rating": None,
            "raw_score": None,
        }

        if not markdown:
            return result

        # 提取情绪评级
        rating_match = cls._SENTIMENT_RATING_PATTERN.search(markdown)
        if rating_match:
            result["raw_rating"] = rating_match.group(0)
            result["mood"] = rating_match.group(1)

        # 提取情绪得分
        score_match = cls._SENTIMENT_SCORE_PATTERN.search(markdown)
        if score_match:
            result["raw_score"] = score_match.group(0)
            score = int(score_match.group(1))
            # 限制在 0-100 范围内
            result["score"] = max(0, min(100, score))

        return result

    @classmethod
    def clean_markdown(cls, markdown: str) -> str:
        """
        清洗 Kimi 返回的 Markdown，去除引言、多余空行等冗余内容。

        清洗规则：
        1. 去除开头的代码块标记（```markdown 等）
        2. 去除开头的问候语/引言（如"以下是晨报..."）
        3. 合并连续空行为单个空行
        4. 去除末尾的代码块标记
        5. 保留免责声明

        参数:
            markdown: 原始 Markdown 字符串

        返回:
            清洗后的 Markdown 字符串
        """
        if not markdown:
            return ""

        text = markdown

        # 1. 去除开头的 ```markdown 或 ``` 标记
        text = re.sub(r"^```markdown\s*\n", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^```\s*\n", "", text)

        # 2. 去除末尾的 ``` 标记
        text = re.sub(r"\n```\s*$", "", text)

        # 3. 去除开头常见的引言（在 # 晨报 或 晨报 2026-04-29 之前的所有内容）
        report_start = re.search(r"^#\s+晨报", text, re.MULTILINE)
        if not report_start:
            # 兼容 Kimi 不输出 # 的情况：查找 "晨报 YYYY-MM-DD"
            report_start = re.search(r"^晨报\s+\d{4}-\d{2}-\d{2}", text, re.MULTILINE)
        if report_start:
            text = text[report_start.start():]

        # 4. 合并连续空行（3个及以上换行合并为2个）
        text = re.sub(r"\n{3,}", "\n\n", text)

        # 5. 去除每行末尾的多余空格
        lines = [line.rstrip() for line in text.split("\n")]
        text = "\n".join(lines)

        # 6. 去除开头和结尾的空白
        text = text.strip()

        return text

    @classmethod
    def extract_sections(cls, markdown: str) -> dict:
        """
        提取 Markdown 中的各章节内容。

        参数:
            markdown: 清洗后的 Markdown 字符串

        返回:
            字典，键为章节标题（不含 ##），值为章节内容。
            特殊键：
            - "_title": 报告主标题（# 晨报 ...）
            - "_disclaimer": 免责声明内容
        """
        result: dict[str, str] = {}

        if not markdown:
            return result

        # 提取主标题
        title_match = re.search(r"^#\s+(.*?)$", markdown, re.MULTILINE)
        if title_match:
            result["_title"] = title_match.group(1).strip()

        # 提取各二级章节
        for match in cls._SECTION_PATTERN.finditer(markdown):
            section_title = match.group(1).strip()
            section_content = match.group(2).strip()
            result[section_title] = section_content

        # 提取免责声明
        disclaimer = cls._extract_disclaimer(markdown)
        if disclaimer:
            result["_disclaimer"] = disclaimer

        return result

    @classmethod
    def _extract_disclaimer(cls, markdown: str) -> Optional[str]:
        """
        从 Markdown 末尾提取免责声明。

        参数:
            markdown: Markdown 字符串

        返回:
            免责声明文本，如果没有则返回 None
        """
        lines = markdown.split("\n")
        disclaimer_lines = []
        collecting = False

        for line in reversed(lines):
            stripped = line.strip()
            if not stripped:
                if collecting:
                    break
                continue

            # 检查是否是免责声明的起始行
            if any(stripped.startswith(marker) for marker in cls._DISCLAIMER_MARKERS):
                collecting = True
                disclaimer_lines.append(stripped)
            elif collecting:
                # 继续向上收集，直到遇到空行或新章节
                if stripped.startswith("## ") or stripped.startswith("# "):
                    break
                disclaimer_lines.append(stripped)

        if disclaimer_lines:
            # 反转回正序
            return "\n".join(reversed(disclaimer_lines))

        return None

    @classmethod
    def process(cls, markdown: str) -> dict:
        """
        一站式处理 Kimi 返回的 Markdown。

        依次执行：清洗 -> 验证 -> 提取情绪 -> 提取章节

        参数:
            markdown: Kimi 返回的原始 Markdown 字符串

        返回:
            处理结果字典：
            {
                "valid": bool,              # 是否通过验证
                "cleaned": str,             # 清洗后的 Markdown
                "sentiment": dict,          # 情绪提取结果
                "sections": dict,           # 章节提取结果
                "error": str | None,        # 错误信息（验证失败时）
            }
        """
        cleaned = cls.clean_markdown(markdown)
        valid = cls.validate_report(cleaned)

        result = {
            "valid": valid,
            "cleaned": cleaned,
            "sentiment": {},
            "sections": {},
            "error": None,
        }

        if not valid:
            result["error"] = "报告缺少必需的 `# 晨报` 标题"
            return result

        result["sentiment"] = cls.extract_sentiment(cleaned)
        result["sections"] = cls.extract_sections(cleaned)

        return result
