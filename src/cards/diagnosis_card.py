"""诊股卡片渲染：将 DiagnosisResult 转为飞书 Card JSON 2.0。"""

from src.feishu.card_sender import build_card_payload


class DiagnosisCardBuilder:
    """构建诊股结果的消息卡片。"""

    # 策略对应的颜色
    STRATEGY_COLORS = {
        "进攻型": "red",
        "防御型": "orange",
        "观望型": "blue",
    }

    def build(self, result) -> dict:
        """从 DiagnosisResult 构建飞书卡片。"""
        color = self.STRATEGY_COLORS.get(result.strategy, "blue")
        alert_emoji = "🔴 " if result.alert_triggered else ""
        title = f"{alert_emoji}{result.name}({result.symbol})"

        elements = []

        # Header 区域：当前价 + 涨跌幅 + 评分
        header_elements = [
            self._text(f"**综合评分**: {result.score}/100"),
            self._text(f"**策略建议**: {result.strategy}"),
        ]
        if result.summary:
            header_elements.append(self._text(f"_{result.summary}_"))
        elements.append(self._column_set(header_elements))

        # 分割线
        elements.append({"tag": "hr"})

        # 关键价位
        price_elements = []
        if result.support is not None:
            price_elements.append(self._text(f"📍 **支撑**: {result.support:.2f} 元"))
        if result.resistance is not None:
            price_elements.append(self._text(f"📍 **压力**: {result.resistance:.2f} 元"))
        if result.stop_loss is not None:
            price_elements.append(self._text(f"🛑 **止损**: {result.stop_loss:.2f} 元"))
        if price_elements:
            elements.append(self._column_set(price_elements))
            elements.append({"tag": "hr"})

        # 警示信息
        if result.alert_triggered and result.alert_msg:
            elements.append({
                "tag": "note",
                "elements": [{"tag": "plain_text", "content": f"⚠️ {result.alert_msg}"}],
            })

        # 分析正文（Markdown）
        if result.analysis_text:
            elements.append(self._text(result.analysis_text))

        # 警告信息
        if result.warnings:
            elements.append({"tag": "hr"})
            warning_text = "\n".join(f"• {w}" for w in result.warnings)
            elements.append({
                "tag": "note",
                "elements": [{"tag": "plain_text", "content": f"数据警告:\n{warning_text}"}],
            })

        return build_card_payload(title=title, color=color, elements=elements)

    def build_error_card(self, symbol: str, error_msg: str) -> dict:
        """构建错误提示卡片。"""
        return build_card_payload(
            title=f"{symbol} 查询失败",
            color="grey",
            elements=[
                {"tag": "div", "text": {"tag": "plain_text", "content": error_msg}},
            ],
        )

    def _text(self, content: str) -> dict:
        """快速构建 Markdown 文本元素。"""
        return {"tag": "div", "text": {"tag": "lark_md", "content": content}}

    def _column_set(self, elements: list) -> dict:
        """将多个元素放入双栏布局。"""
        return {
            "tag": "column_set",
            "flex_mode": "none",
            "background_style": "default",
            "columns": [
                {
                    "tag": "column",
                    "width": "weighted",
                    "weight": 1,
                    "elements": elements,
                }
            ],
        }
