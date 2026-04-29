"""晨报卡片渲染：将 MorningReport 转为飞书 Card JSON 2.0。"""

from src.feishu.card_sender import build_card_payload


class MorningReportCardBuilder:
    """构建晨报的消息卡片。

    按章节拆分内容，优化表格渲染（制表符表格转 Markdown 表格），
    增加 emoji 图标、视觉层级和颜色区分，提升数据可读性。
    """

    SENTIMENT_COLOR_MAP = {
        "乐观": "green",
        "中性": "blue",
        "谨慎": "orange",
        "悲观": "red",
    }

    # 一级章节
    PRIMARY_SECTIONS = [
        "全球市场概览",
        "A股盘前要点",
        "情绪评级",
        "持仓关注",
        "操作策略",
    ]

    # 二级子章节
    SUB_SECTIONS = ["宏观政策", "行业动态", "板块前瞻"]

    # 章节图标映射
    SECTION_ICONS = {
        "全球市场概览": "🌍",
        "A股盘前要点": "🇨🇳",
        "宏观政策": "📜",
        "行业动态": "🏭",
        "板块前瞻": "🔭",
        "情绪评级": "📊",
        "持仓关注": "💼",
        "操作策略": "🎯",
    }

    def build(self, report) -> dict:
        """从 MorningReport 构建飞书卡片。"""
        title = f"📰 投资晨报 {report.date}"

        # 情绪数据提取
        sentiment_mood = getattr(report, "sentiment", None)
        if isinstance(sentiment_mood, dict):
            mood = sentiment_mood.get("mood", "")
            score = sentiment_mood.get("score")
        else:
            mood = sentiment_mood or ""
            score = None
        color = self.SENTIMENT_COLOR_MAP.get(mood, "blue")

        elements = []

        # ========== 顶部情绪标签 ==========
        if mood:
            tag_text = f"情绪: {mood}"
            if score is not None:
                tag_text += f"  |  得分: {score}/100"
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "plain_text",
                    "content": tag_text,
                    "text_size": "heading",
                    "text_color": color,
                },
            })
            elements.append({"tag": "hr"})

        # ========== 拆分正文与免责声明 ==========
        body_text, disclaimer = self._split_disclaimer(report.content or "")

        # 提取并移除数据截止行 / 主标题行
        meta_line = ""
        lines = body_text.split("\n")
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if "数据截止" in stripped and "上一交易日" in stripped:
                meta_line = stripped
            elif stripped.startswith("晨报 ") and len(stripped) < 30:
                continue
            else:
                new_lines.append(line)

        if meta_line:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "plain_text",
                    "content": meta_line,
                    "text_size": "notation",
                    "text_color": "grey",
                },
            })

        body_text = "\n".join(new_lines).strip()

        # ========== 按章节渲染 ==========
        sections = self._parse_sections(body_text)
        for i, section in enumerate(sections):
            level = section.get("level", 1)
            section_title = section.get("title", "")
            section_lines = section.get("lines", [])

            # 章节标题
            if section_title:
                icon = self.SECTION_ICONS.get(section_title, "")
                title_text = f"{icon} {section_title}" if icon else section_title
                text_size = "heading" if level == 1 else "normal"
                text_color = "blue" if level == 1 else "grey"
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "plain_text",
                        "content": title_text,
                        "text_size": text_size,
                        "text_color": text_color,
                    },
                })

            # 章节正文（格式化预处理）
            raw_body = "\n".join(section_lines).strip()
            if raw_body:
                formatted_body = self._format_section_body(raw_body, section_title)
                elements.append({
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": formatted_body},
                })

            # 智能分割线
            next_section = sections[i + 1] if i + 1 < len(sections) else None
            next_level = next_section.get("level") if next_section else None
            skip_hr = False
            if level == 1 and not raw_body and next_level == 2:
                skip_hr = True
            if level == 2 and next_level == 2:
                skip_hr = True
            if not skip_hr:
                elements.append({"tag": "hr"})

        # ========== 免责声明 ==========
        if disclaimer:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "plain_text",
                    "content": f"🛡️ {disclaimer}",
                    "text_size": "notation",
                    "text_color": "grey",
                },
            })

        # ========== 警告信息 ==========
        if report.warnings:
            warning_text = "\n".join(f"• {w}" for w in report.warnings)
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "plain_text",
                    "content": f"⚠️ 数据警告:\n{warning_text}",
                    "text_size": "notation",
                    "text_color": "orange",
                },
            })

        return build_card_payload(title=title, color=color, elements=elements)

    # ------------------------------------------------------------------
    # 正文格式化
    # ------------------------------------------------------------------

    def _format_section_body(self, body: str, section_title: str = "") -> str:
        """对章节正文进行格式化预处理。

        1. 把制表符分隔的表格转换为标准 Markdown 表格
        2. 跳过单独的 "表格" 标记行
        3. "数据缺失" 内容转为引用块（灰色背景）
        4. 情绪评级章节对关键信息加粗高亮
        5. "小结：" 行加粗
        """
        lines = body.split("\n")
        result = []
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # 跳过单独的 "表格" 标记行
            if stripped == "表格":
                i += 1
                continue

            # 检测制表符表格块（连续多行包含制表符）
            if "\t" in line:
                table_lines = [line]
                j = i + 1
                while j < len(lines) and "\t" in lines[j]:
                    table_lines.append(lines[j])
                    j += 1
                md_table = self._convert_tab_table(table_lines)
                if md_table:
                    result.append(md_table)
                i = j
                continue

            # 数据缺失 → 引用块（飞书 lark_md 会渲染为灰色背景）
            if "数据缺失" in stripped:
                result.append(f"> ⚠️ {stripped}")
                i += 1
                continue

            # 小结行加粗
            if stripped.startswith("小结："):
                result.append(f"**{stripped}**")
                i += 1
                continue

            # 情绪评级章节高亮
            if section_title == "情绪评级":
                if stripped.startswith("判断理由"):
                    result.append(f"**{stripped}**")
                    i += 1
                    continue

            result.append(line)
            i += 1

        return "\n".join(result)

    def _convert_tab_table(self, lines: list[str]) -> str:
        """将制表符分隔的行列表转换为 Markdown 表格。"""
        if not lines:
            return ""

        # 按制表符拆分列
        rows = [line.split("\t") for line in lines]
        max_cols = max(len(r) for r in rows)

        # 补齐列数
        for r in rows:
            while len(r) < max_cols:
                r.append("")

        md_lines = []
        for idx, row in enumerate(rows):
            cells = [c.strip() for c in row]
            md_lines.append("| " + " | ".join(cells) + " |")
            if idx == 0:
                # 分隔行：全部左对齐
                md_lines.append("| " + " | ".join([":--"] * max_cols) + " |")

        return "\n".join(md_lines)

    # ------------------------------------------------------------------
    # 内容拆分辅助方法
    # ------------------------------------------------------------------

    def _split_disclaimer(self, content: str) -> tuple[str, str]:
        """从内容末尾分离免责声明。"""
        lines = content.split("\n")
        disclaimer_lines = []
        body_lines = []
        found = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("免责声明"):
                found = True
                disclaimer_lines.append(stripped)
            elif found and stripped:
                disclaimer_lines.append(stripped)
            elif found and not stripped:
                pass
            else:
                body_lines.append(line)

        if not found:
            for i in range(len(lines) - 1, -1, -1):
                if "免责声明" in lines[i]:
                    body_lines = lines[:i]
                    disclaimer_lines = lines[i:]
                    break

        body = "\n".join(body_lines).strip()
        disclaimer = "\n".join(disclaimer_lines).strip()
        return body, disclaimer

    def _parse_sections(self, content: str) -> list[dict]:
        """把晨报正文按章节拆分为结构化数据。"""
        text = content.replace("\r\n", "\n")
        lines = text.split("\n")
        sections: list[dict] = []
        current: dict = {"title": "", "level": 1, "lines": []}

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("晨报 ") and len(stripped) < 30:
                continue

            if "数据截止" in stripped and "上一交易日" in stripped:
                if current["lines"] or current["title"]:
                    sections.append(current)
                sections.append({"title": "", "level": 0, "lines": [stripped]})
                current = {"title": "", "level": 1, "lines": []}
                continue

            if stripped in self.PRIMARY_SECTIONS:
                if current["lines"] or current["title"]:
                    sections.append(current)
                current = {"title": stripped, "level": 1, "lines": []}
                continue

            if stripped in self.SUB_SECTIONS:
                if current["lines"] or current["title"]:
                    sections.append(current)
                current = {"title": stripped, "level": 2, "lines": []}
                continue

            current["lines"].append(line)

        if current["lines"] or current["title"]:
            sections.append(current)

        return sections

    def build_delay_warning(self, data_time: str) -> dict:
        """构建晨报延迟警告卡片。"""
        return build_card_payload(
            title="⏰ 晨报生成延迟",
            color="orange",
            elements=[
                {
                    "tag": "div",
                    "text": {
                        "tag": "plain_text",
                        "content": f"晨报正在生成中，预计很快送达。\n数据截止 {data_time}",
                    },
                },
            ],
        )
