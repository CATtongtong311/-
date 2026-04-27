"""晨报卡片渲染：将 MorningReport 转为飞书 Card JSON 2.0。"""

from src.feishu.card_sender import build_card_payload


class MorningReportCardBuilder:
    """构建晨报的消息卡片。"""

    def build(self, report) -> dict:
        """从 MorningReport 构建飞书卡片。"""
        title = f"📰 投资晨报 {report.date}"
        color = "blue"

        elements = []

        # 晨报正文（Markdown）
        if report.content:
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": report.content},
            })
        else:
            elements.append({
                "tag": "div",
                "text": {"tag": "plain_text", "content": "晨报内容为空"},
            })

        # 警告信息
        if report.warnings:
            elements.append({"tag": "hr"})
            warning_text = "\n".join(f"• {w}" for w in report.warnings)
            elements.append({
                "tag": "note",
                "elements": [{"tag": "plain_text", "content": f"⚠️ 数据警告:\n{warning_text}"}],
            })

        return build_card_payload(title=title, color=color, elements=elements)

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
