"""
Kimi 晨报生成超级 Prompt 模板

该模块负责组装发送给 Kimi Agent 的完整 Prompt，
Kimi 将基于此 Prompt 直接生成完整的晨报 Markdown。
"""

from typing import Any

# ---------------------------------------------------------------------------
# 超级 Prompt 模板
# ---------------------------------------------------------------------------
KIMI_MORNING_REPORT_PROMPT = """你是一位资深金融分析师，擅长撰写每日开盘前的晨报。
今天是 {date}，上一交易日是 {yesterday}。数据截止时间为 {fetch_time}。

请严格基于以下真实数据，生成一份完整的晨报 Markdown。禁止编造任何数据，
如果某类数据缺失，请明确标注"数据缺失"，不要自行推测。

---

## 用户持仓

{holdings}

---

## 关注板块

{watch_sectors}

---

## 隔夜全球市场数据

{market_data}

---

## 持仓个股相关新闻

{holdings_news}

---

## 输出格式要求

请输出完整的 Markdown 格式晨报，必须包含以下章节（按顺序）：

# 晨报 {date}

## 全球市场概览
- 美股三大指数、纳斯达克中国金龙指数、富时A50期指、汇率、大宗商品、美债收益率等关键数据
- 每项用一句话概括走势

## A股盘前要点
- 隔夜重要消息、政策动向
- 分两类，每类最多 3 条，每条包含"标题 + 一句话影响解读"：
  1. **宏观政策**
  2. **行业动态**

## 板块前瞻
- 针对用户关注的板块，给出今日展望
- 每个板块 2-3 句话，说明逻辑

## 情绪评级
- **情绪评级**：乐观 / 中性 / 谨慎（三选一）
- **情绪得分**：XX/100（0-100 的整数）
- **判断理由**：2-3 句话说明依据

## 持仓关注
- 针对用户持仓中的个股，列出昨夜至今的重大消息
- 无重大事件则标注"无重大事件"
- 每条包含：股票名称 + 事件简述 + 影响判断

## 操作策略
- 今日操作建议，最多 3 条，每条 1-2 句话
- 可以是仓位建议、板块配置、风险提示等

---

**免责声明**：本晨报仅供参考，不构成投资建议。

要求：
1. 数据必须真实，禁止编造涨跌幅、指数点位等数字
2. 分析要简洁有力，避免冗长
3. 情绪评级和得分必须基于数据客观判断
4. Markdown 格式规范，层级清晰
5. 请直接输出一个 Markdown 文档给我。
"""


def format_market_data(snapshot: dict) -> str:
    """
    将市场数据字典格式化为 Markdown 表格或列表。

    参数:
        snapshot: 市场快照字典，结构示例：
            {
                "dow_jones": {"close": 40200, "change": "+0.45%"},
                "sp500": {"close": 5200, "change": "+0.32%"},
                "nasdaq": {"close": 16000, "change": "-0.12%"},
                ...
            }

    返回:
        Markdown 格式的市场数据字符串
    """
    if not snapshot:
        return "_市场数据缺失_"

    lines = ["| 市场/指数 | 收盘/现价 | 涨跌幅 |", "| :-- | --: | --: |"]
    name_map = {
        "dow_jones": "道琼斯",
        "sp500": "标普 500",
        "nasdaq": "纳斯达克",
        "nasdaq_china": "纳斯达克中国金龙",
        "ftse_a50": "富时 A50 期指",
        "shanghai": "上证指数",
        "shenzhen": "深证成指",
        "chi_next": "创业板指",
        "hsi": "恒生指数",
        "nikkei": "日经 225",
        "usd_cny": "美元/人民币",
        "gold": "现货黄金",
        "crude_oil": "WTI 原油",
        "btc": "比特币",
    }

    for key, data in snapshot.items():
        name = name_map.get(key, key)
        close = data.get("close", "-")
        change = data.get("change", "-")
        lines.append(f"| {name} | {close} | {change} |")

    return "\n".join(lines)


def format_holdings(portfolio: dict) -> str:
    """
    格式化用户持仓列表为 Markdown。

    参数:
        portfolio: 持仓字典，结构示例：
            {
                "holdings": [
                    {"symbol": "600519", "name": "贵州茅台", "cost_price": 1600, ...}
                ],
                "watch_sectors": ["新能源 / 锂电池", "AI 算力"]
            }

    返回:
        Markdown 格式的持仓信息字符串
    """
    holdings = portfolio.get("holdings", [])
    if not holdings:
        return "_当前无持仓_"

    lines = ["| 代码 | 名称 | 成本价 | 持仓数量 |", "| :-- | :-- | --: | --: |"]
    for h in holdings:
        symbol = h.get("symbol", "-")
        name = h.get("name", "-")
        cost = h.get("cost_price", "-")
        qty = h.get("quantity", "-")
        lines.append(f"| {symbol} | {name} | {cost} | {qty} |")

    return "\n".join(lines)


def format_watch_sectors(portfolio: dict) -> str:
    """
    格式化关注板块列表为 Markdown 列表。

    参数:
        portfolio: 持仓字典，包含 watch_sectors 字段

    返回:
        Markdown 列表格式的关注板块字符串
    """
    sectors = portfolio.get("watch_sectors", [])
    if not sectors:
        return "_当前无关注板块_"

    lines = []
    for sector in sectors:
        lines.append(f"- {sector}")
    return "\n".join(lines)


def format_holdings_news(news_dict: dict) -> str:
    """
    格式化持仓个股新闻为 Markdown。

    参数:
        news_dict: 持仓新闻字典，结构示例：
            {
                "600519": [
                    {"title": "贵州茅台一季度业绩超预期", "summary": "营收同比增长 15%..."}
                ]
            }

    返回:
        Markdown 格式的持仓新闻字符串
    """
    if not news_dict:
        return "_持仓个股暂无新闻_"

    lines = []
    for symbol, news_list in news_dict.items():
        lines.append(f"**{symbol}**")
        if not news_list:
            lines.append("- 暂无相关新闻")
        else:
            for news in news_list:
                title = news.get("title", "-")
                summary = news.get("summary", "")
                if summary:
                    lines.append(f"- **{title}**：{summary}")
                else:
                    lines.append(f"- {title}")
        lines.append("")

    return "\n".join(lines).rstrip()


def build_kimi_prompt(input_data: dict) -> str:
    """
    组装完整的 Kimi 晨报生成 Prompt。

    参数:
        input_data: 输入数据字典，结构如下：
            {
                "date": "2026-04-28",
                "yesterday": "2026-04-27",
                "market_snapshot": {
                    "dow_jones": {"close": 40200, "change": "+0.45%"},
                    ...
                },
                "portfolio": {
                    "holdings": [{"symbol": "600519", "name": "贵州茅台", ...}],
                    "watch_sectors": ["新能源 / 锂电池", "AI 算力"]
                },
                "holdings_news": {"600519": [{"title": "...", "summary": "..."}]},
                "fetch_time": "08:25"
            }

    返回:
        组装完成的 Prompt 字符串，可直接发送给 Kimi Agent
    """
    date = input_data.get("date", "")
    yesterday = input_data.get("yesterday", "")
    fetch_time = input_data.get("fetch_time", "")
    market_snapshot = input_data.get("market_snapshot", {})
    portfolio = input_data.get("portfolio", {})
    holdings_news = input_data.get("holdings_news", {})

    market_data_md = format_market_data(market_snapshot)
    holdings_md = format_holdings(portfolio)
    watch_sectors_md = format_watch_sectors(portfolio)
    holdings_news_md = format_holdings_news(holdings_news)

    prompt = KIMI_MORNING_REPORT_PROMPT.format(
        date=date,
        yesterday=yesterday,
        market_data=market_data_md,
        holdings=holdings_md,
        watch_sectors=watch_sectors_md,
        holdings_news=holdings_news_md,
        fetch_time=fetch_time,
    )

    return prompt
