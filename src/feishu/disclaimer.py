"""免责声明与卡片 footer 注入。"""

from copy import deepcopy
from datetime import datetime

DISCLAIMER_TEXT = "AI生成内容仅供参考，不构成投资建议"


def inject_footer(card_dict: dict, data_time: str | None = None) -> dict:
    """在卡片末尾注入数据截止时间和免责声明。"""
    card = deepcopy(card_dict)
    if data_time is None:
        data_time = datetime.now().strftime("%H:%M")

    footer_elements = [
        {"tag": "div", "text": {"tag": "lark_md", "content": f"**数据截止 {data_time}**"}},
        {"tag": "div", "text": {"tag": "lark_md", "content": f"_{DISCLAIMER_TEXT}_"}},
    ]

    if "body" not in card:
        card["body"] = {"elements": []}
    if "elements" not in card["body"]:
        card["body"]["elements"] = []

    card["body"]["elements"].extend(footer_elements)
    return card
