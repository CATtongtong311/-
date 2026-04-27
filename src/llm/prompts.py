"""LLM Prompt 模板：诊股与晨报。"""

DIAGNOSIS_SYSTEM = """你是一位资深股票分析师，擅长技术面、基本面、资金面、情绪面四维度综合分析。
你的分析必须基于用户提供的实时数据，禁止编造任何股价、财务数据或新闻事件。
如果数据缺失，直接回答"数据暂不可用"。

输出格式要求（严格使用 Markdown）：
## 综合评分：X/100
## 策略建议：进攻型/防御型/观望型
一句话总结：...

## 技术速览
- 趋势判断：...
- 关键价位：支撑 XX 元 / 压力 XX 元
- 止损参考：XX 元（-X%）

## 多派会诊
- 技术面：...
- 基本面：...
- 资金面：...
- 情绪面：...

## 操作建议
1. ...
2. ...
"""


def build_diagnosis_prompt(
    symbol: str,
    name: str,
    quote: dict,
    news: list[dict],
    holding: dict | None = None,
) -> str:
    """构建诊股 Prompt。"""
    lines = [
        f"请对以下股票进行四维度综合分析：",
        f"",
        f"**股票代码**: {symbol}",
        f"**股票名称**: {name}",
        f"",
        f"**实时行情数据**:",
        f"- 开盘价: {quote.get('open', 'N/A')}",
        f"- 最高价: {quote.get('high', 'N/A')}",
        f"- 最低价: {quote.get('low', 'N/A')}",
        f"- 当前价: {quote.get('close', 'N/A')}",
        f"- 成交量: {quote.get('volume', 'N/A')}",
        f"- 涨跌幅: {quote.get('change_pct', 'N/A')}%",
        f"- 换手率: {quote.get('turnover', 'N/A')}%",
        f"",
    ]

    if holding:
        lines.extend([
            f"**用户持仓信息**:",
            f"- 成本价: {holding.get('cost_price', 'N/A')} 元",
            f"- 持仓数量: {holding.get('quantity', 'N/A')} 股",
            f"- 所属板块: {holding.get('sector', 'N/A')}",
            f"- 备注: {holding.get('notes', 'N/A')}",
            f"",
        ])

    if news:
        lines.append(f"**近期相关新闻/公告**:")
        for i, item in enumerate(news[:5], 1):
            title = item.get("title", "")
            summary = item.get("summary", "")[:100]
            lines.append(f"{i}. {title} - {summary}")
        lines.append("")

    lines.append("请严格按照系统指令的输出格式进行分析。")
    return "\n".join(lines)


MORNING_REPORT_SYSTEM = """你是一位资深市场分析师，每天早上为用户生成个性化的投资晨报。
你的分析必须基于用户提供的实时数据，禁止编造任何指数点位、股价或新闻事件。
如果数据缺失，直接回答"数据暂不可用"。

输出格式要求（严格使用 Markdown）：
# 晨报 YYYY-MM-DD

## 隔夜全球市场速览
- 美股：...
- 港股：...
- 外汇/美债：...

## 持仓个股重大事件
（逐只分析持仓股的重要新闻和技术面变化）

## 今日重点板块前瞻
（分析用户关注板块的资金面和题材热度）
"""


def build_morning_report_prompt(
    portfolio: dict,
    market_snapshot: dict,
    holdings_news: dict[str, list[dict]],
) -> str:
    """构建晨报 Prompt。"""
    lines = [
        "请生成今日投资晨报。",
        "",
        "**全球市场数据**:",
    ]

    # 全球市场
    for key, label in [
        ("dow_jones", "道琼斯"),
        ("sp500", "标普500"),
        ("nasdaq", "纳斯达克"),
        ("hsi_futures", "恒生期货"),
        ("usdx", "美元指数"),
        ("usdcnh", "离岸人民币"),
        ("us_10y", "10Y美债收益率"),
    ]:
        data = market_snapshot.get(key)
        if data:
            close = data.get("close", "N/A")
            change = data.get("change", "N/A")
            lines.append(f"- {label}: {close} ({change})")
        else:
            lines.append(f"- {label}: 数据暂不可用")

    lines.extend([
        "",
        "**用户持仓**:",
    ])

    for h in portfolio.get("holdings", []):
        lines.append(f"- {h.get('name', '')}({h.get('symbol', '')}): 成本价 {h.get('cost_price', 'N/A')} 元, 数量 {h.get('quantity', 'N/A')} 股, 板块 {h.get('sector', '')}")

    lines.extend([
        "",
        "**关注板块**:",
    ])
    for sector in portfolio.get("watch_sectors", []):
        lines.append(f"- {sector}")

    if holdings_news:
        lines.extend([
            "",
            "**持仓个股新闻汇总**:",
        ])
        for symbol, news_list in holdings_news.items():
            if news_list:
                lines.append(f"\n{symbol}:")
                for item in news_list[:3]:
                    title = item.get("title", "")
                    lines.append(f"  - {title}")

    lines.extend([
        "",
        "请严格按照系统指令的输出格式生成晨报。",
    ])

    return "\n".join(lines)
