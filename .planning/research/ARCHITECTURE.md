# 架构研究：智能金融晨报与交互分析系统

**领域:** 个人智能金融助手 / 飞书机器人
**研究日期:** 2026-04-27
**置信度:** HIGH（基于已验证的技术栈选择、飞书官方文档、PITFALLS.md 社区实践总结）

---

## 系统总览

本项目是一个**单进程、单线程（异步事件驱动）**的 Python 应用。核心设计原则：**能串行就不并行，能内存就不外存，能单文件就不分布式**。这是个人 Demo，不是微服务。

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              外部服务层                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  飞书开放平台  │  │  Tushare    │  │  AKShare    │  │  Claude / Kimi API  │ │
│  │  (WebSocket) │  │  (主数据源)  │  │  (备用数据源)│  │  (LLM 分析生成)      │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
└─────────┼────────────────┼────────────────┼────────────────────┼────────────┘
          │                │                │                    │
          ▼                ▼                ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              应用核心层                                       │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        FeishuGateway                                │   │
│  │  ├─ WebSocket 长连接管理（心跳、重连、事件监听）                      │   │
│  │  ├─ 消息解析器（@机器人 / 股票代码 / 中文简称提取）                   │   │
│  │  └─ 卡片发送器（模板变量填充、大小预检、分片策略）                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        MasterAgent                                  │   │
│  │  ├─ 意图路由（诊股 / 晨报 / 持仓查询 / 帮助）                        │   │
│  │  ├─ 上下文组装（持仓 MD + 用户查询 + 历史对话）                      │   │
│  │  ├─ 单 Prompt 多维度分析（技术/基本面/资金面/情绪面）                │   │
│  │  └─ 合规包装（免责声明前置、语气弱化、风险分级）                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        DataFetcher                                  │   │
│  │  ├─ TushareAdapter（主源：日线、财务、公告）                         │   │
│  │  ├─ AkshareAdapter（备用：指数、板块、美股）                         │   │
│  │  ├─ SinaAdapter（备用：实时行情、资金流向）                          │   │
│  │  ├─ 数据校验层（OHLC 合法性、停牌检测、复权统一）                    │   │
│  │  └─ 调用计数器（Tushare 额度监控、自动降级）                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        CardBuilder                                  │   │
│  │  ├─ 诊股卡片模板（Header + 四维度分析 + 操作建议 + 免责声明）         │   │
│  │  ├─ 晨报卡片模板（全球市场 + 持仓事件 + 板块前瞻 + 红标警示）         │   │
│  │  ├─ 大小预检（>25KB 触发裁剪 / 折叠 / 分片）                        │   │
│  │  └─ 变量渲染（模板 ID + 变量字典 → 完整卡片 JSON）                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Scheduler                                    │   │
│  │  ├─ APScheduler BackgroundScheduler（与 WebSocket 共存）             │   │
│  │  ├─ 交易日历过滤（调用 Tushare trade_cal 判断休市）                  │   │
│  │  ├─ 晨报生成任务（08:30 触发，独立线程执行不阻塞主循环）              │   │
│  │  └─ 心跳自检（每 5 分钟发送测试消息验证通路）                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              本地持久层                                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐ │
│  │  SQLite (peewee) │  │  持仓 Markdown   │  │      配置文件 (.env)         │ │
│  │  ├─ api_calls    │  │  portfolio.md    │  │  ├─ 飞书 App ID/Secret      │ │
│  │  ├─ daily_cache  │  │  ├─ 股票代码      │  │  ├─ Tushare Token           │ │
│  │  ├─ error_logs   │  │  ├─ 成本价        │  │  ├─ Claude/Kimi API Key     │ │
│  │  └─ holdings_snap│  │  ├─ 持仓量        │  │  └─ 用户偏好设置            │ │
│  │                 │  │  └─ 关注板块      │  │                             │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 组件边界与职责

### 1. FeishuGateway — 飞书连接网关

**职责范围：** 只负责"连接飞书、收发消息"，不处理业务逻辑。

| 子模块 | 职责 | 不做的 |
|--------|------|--------|
| WebSocketManager | 建立/维护/重连长连接，处理 Ping/Pong，指数退避重连 | 不解析消息内容 |
| MessageParser | 从 `im.message.receive_v1` 事件提取：@目标、纯文本内容、发送者 ID | 不识别股票代码（交给 MasterAgent） |
| CardSender | 发送/更新消息卡片，预检 30KB 限制，超限时分片 | 不构建卡片内容（交给 CardBuilder） |

**对外通信：**
- 上接：飞书开放平台 WebSocket 事件流
- 下交：将解析后的用户请求（`UserQuery` 对象）投递给 MasterAgent
- 回调：MasterAgent 返回 `CardPayload` 后，调用 CardSender 发送

**关键约束：**
- 飞书要求按钮回调 3 秒内响应 → 复杂分析必须先发送"分析中..."占位卡片，异步更新结果
- 群聊中必须 @机器人才能触发 → MessageParser 需过滤非 @消息

---

### 2. MasterAgent — 中央调度器

**职责范围：** 唯一入口，负责"理解用户意图、协调数据、生成回复"。

| 子模块 | 职责 | 不做的 |
|--------|------|--------|
| IntentRouter | 根据关键词路由：诊股 / 晨报 / 持仓 / 帮助 / 未知 | 不直接调用数据源 |
| ContextAssembler | 每次查询时读取 portfolio.md，组装"持仓上下文 + 用户输入 + 系统指令" | 不缓存持仓（按用户要求每次读取） |
| LLMCoordinator | 统一封装 Claude/Kimi 调用，降级策略，超时控制（10 秒） | 不处理金融数据获取 |
| ComplianceWrapper | 免责声明前置、输出审计（扫描禁止词汇）、风险分级标记 | 不修改 LLM 分析结论 |

**核心设计决策：单 Agent 而非多 Agent**

第一期严格使用**单 Agent + 多维度 Prompt**，而非物理拆分为 Tech/Funda/Quant/Senti 四个 Agent。

```python
# 单 Prompt 多维度分析示例
SYSTEM_PROMPT = """你是一位资深股票分析师。基于以下实时数据，从四个维度分析 {stock_name}({stock_code})：

## 技术面
- 当前价格: {price}, 涨跌幅: {change_pct}
- 5日/10日/20日均线: {ma5}/{ma10}/{ma20}
- MACD/RSI/KDJ: {macd}/{rsi}/{kdj}
- 成交量较20日均量: {vol_ratio}

## 基本面
- 市盈率(TTM): {pe_ttm}, 市净率: {pb}
- 最新季度营收同比: {revenue_yoy}
- 所属行业: {industry}

## 资金面
- 主力资金流向: {main_flow}
- 融资融券余额变化: {margin_change}

## 情绪面
- 近7日新闻情绪: {sentiment}
- 机构研报评级分布: {ratings}

## 持仓关联（如为持仓股）
- 成本价: {cost_price}, 当前盈亏: {pnl_pct}
- 距离成本价±5%警示线: {alert_status}

请输出结构化分析，最后给出明确操作建议（观望/关注/减仓/加仓）。
注意：使用客观描述语气，禁止使用"必涨""目标价""强烈建议买入"等词汇。
"""
```

**对外通信：**
- 接收：FeishuGateway 投递的 `UserQuery`
- 调用：DataFetcher 获取实时数据，LLM API 生成分析
- 返回：将 `CardPayload` 交回 FeishuGateway 发送

---

### 3. DataFetcher — 数据获取与适配层

**职责范围：** 统一封装所有外部金融数据接口，对外提供"按股票代码获取全维度数据"的单一接口。

| 子模块 | 职责 | 数据源 |
|--------|------|--------|
| TushareAdapter | A股日线、财务指标、公告、交易日历 | Tushare Pro API |
| AkshareAdapter | 板块数据、美股指数、汇率、港股 | AKShare（免费备用） |
| SinaAdapter | 实时行情、资金流向、新闻快讯 | 新浪财经（非官方，备用） |
| DataValidator | OHLC 合法性检查、停牌检测、复权方式统一、空值处理 | 无（纯校验逻辑） |
| QuotaManager | Tushare 调用计数、额度预警、自动降级到备用源 | SQLite 计数表 |

**统一接口设计：**

```python
class DataFetcher:
    def get_stock_full_data(self, code: str) -> StockData:
        """
        对外唯一接口。内部按优先级调用各适配器，自动降级。
        返回已校验的标准化数据对象。
        """
        pass

@dataclass
class StockData:
    code: str           # 规范化代码，如 "000625.SZ"
    name: str           # 中文简称
    price: float        # 最新价
    ohlc: OHLC          # 开高低收（前复权）
    volume: int         # 成交量
    indicators: TechIndicators   # 均线/MACD/RSI/KDJ
    fundamentals: FundaMetrics   # PE/PB/营收同比
    capital_flow: CapitalFlow    # 主力流向/融资融券
    sentiment: SentimentScore    # 新闻情绪/研报评级
    is_halted: bool              # 是否停牌
    alerts: list[Alert]          # 红标警示列表
```

**关键约束：**
- 所有股票代码必须规范化（6位数字 + .SZ/.SH）
- 停牌股票明确标记，不计算技术指标
- 统一使用前复权数据
- Tushare 接近额度上限时自动切换 AKShare

---

### 4. CardBuilder — 卡片构建器

**职责范围：** 将结构化数据渲染为飞书消息卡片 JSON。

| 子模块 | 职责 |
|--------|------|
| TemplateRegistry | 管理卡片模板 ID（诊股卡片、晨报卡片、帮助卡片、错误卡片） |
| VariableRenderer | 将数据对象填充到模板变量字典 |
| SizeGuard | 预检卡片大小，>25KB 时触发裁剪策略 |

**卡片模板策略：**

推荐使用**飞书卡片搭建工具**可视化设计后获取 `template_id`，代码中仅传递变量：

```python
# 诊股卡片变量示例
diagnosis_variables = {
    "stock_name": "中芯国际",
    "stock_code": "688981.SH",
    "price": "56.30",
    "change_pct": "+2.35%",
    "tech_summary": "短期均线多头排列，MACD金叉...",
    "funda_summary": "PE(TTM) 85.3，高于行业均值...",
    "capital_summary": "主力净流入 1.2亿...",
    "sentiment_summary": "机构评级以买入为主...",
    "suggestion": "关注",           # 观望/关注/减仓/加仓
    "suggestion_color": "orange",   # 灰/蓝/橙/红
    "is_holding": True,
    "cost_price": "54.00",
    "pnl_pct": "+4.26%",
    "alert_badge": "距离成本价+5%警示线",
    "disclaimer": "AI生成内容仅供参考，不构成投资建议"
}
```

**大小超限处理策略（优先级从高到低）：**
1. 将次要内容折叠到"查看详情"按钮后
2. 用 `plain_text` 替代 `lark_md` 减少样式开销
3. 分段发送（先发送摘要卡片，再发送详情卡片）

---

### 5. Scheduler — 定时任务调度

**职责范围：** 晨报生成与系统自检。

| 子模块 | 职责 |
|--------|------|
| TradeCalendar | 调用 Tushare `trade_cal` 判断当日是否开市，休市日跳过 |
| MorningBriefTask | 08:30 触发，独立线程执行晨报生成全流程 |
| HeartbeatTask | 每 5 分钟发送飞书测试消息，验证通路 |
| HealthReporter | 任务执行后发送成功/失败状态到飞书 |

**关键设计：**
- 晨报生成在**独立线程**中执行，不阻塞 WebSocket 主循环
- APScheduler 配置：`misfire_grace_time=300`, `coalesce=True`, `max_instances=1`
- 失败时发送告警卡片到飞书，而非仅记录日志

---

### 6. PortfolioReader — 持仓文档读取器

**职责范围：** 每次查询时读取并解析 portfolio.md。

**MD 格式模板（用户必须遵循）：**

```markdown
---
updated_at: 2026-04-27
---

# 持仓清单

| 代码 | 名称 | 成本价 | 持仓量 | 警示阈值 | 关注板块 |
|------|------|--------|--------|----------|----------|
| 688981 | 中芯国际 | 54.00 | 1000 | 5% | 半导体 |
| 002371 | 北方华创 | 320.00 | 500 | 5% | 半导体设备 |
| 300502 | 新易盛 | 85.00 | 800 | 5% | 光模块/CPO |

# 关注板块（非持仓但跟踪）
- AI算力
- 液冷
- 商业航天
```

**解析流程：**
1. 读取文件 → 提取 YAML frontmatter（更新时间）
2. 解析 Markdown 表格 → 转换为 `list[Holding]`
3. 格式校验：代码必须为 6 位数字，成本价必须为正数
4. 校验失败 → 发送告警卡片到飞书，回退到 SQLite 缓存
5. 校验成功 → 发送确认消息到飞书（"已读取持仓：中芯国际 x 1000股"）

**关键约束：**
- 每次查询都重新读取（用户明确要求，不缓存）
- SQLite 中保存上次成功解析的持仓，作为 MD 解析失败时的回退

---

### 7. SQLite 本地存储

**职责范围：** 轻量级持久化，单文件零运维。

| 表名 | 用途 | 数据量预估 |
|------|------|-----------|
| `api_calls` | 记录每次外部 API 调用（来源、耗时、是否成功） | <1000 条/月 |
| `daily_cache` | 日线数据本地缓存，避免重复拉取 | <50MB/年 |
| `error_logs` | 结构化错误记录（便于排查） | <1000 条/月 |
| `holdings_snap` | 持仓解析成功后的快照（MD 失败时回退） | <100 条/年 |
| `quota_usage` | Tushare 每日调用计数 | <365 条/年 |

**ORM 模型（peewee）：**

```python
from peewee import SqliteDatabase, Model, CharField, DateTimeField, FloatField, IntegerField, BooleanField

db = SqliteDatabase('finance_bot.db')

class BaseModel(Model):
    class Meta:
        database = db

class ApiCall(BaseModel):
    source = CharField()           # 'tushare' / 'akshare' / 'claude' / 'kimi'
    endpoint = CharField()         # 接口名称
    params = CharField()           # 参数摘要
    success = BooleanField()
    duration_ms = IntegerField()
    created_at = DateTimeField()

class DailyCache(BaseModel):
    code = CharField()
    trade_date = CharField()       # '20260427'
    data_json = CharField()        # 日线数据 JSON
    fetched_at = DateTimeField()
```

---

## 数据流

### 流 1：诊股交互（@机器人 → 卡片回复）

```
用户@机器人输入 "600519" 或 "贵州茅台"
    │
    ▼
FeishuGateway.MessageParser
    │  提取纯文本内容，过滤非@消息
    ▼
MasterAgent.IntentRouter
    │  识别为"诊股意图"
    ▼
MasterAgent.ContextAssembler
    │  1. 调用 PortfolioReader 读取 portfolio.md
    │  2. 判断是否为持仓股（是 → 附加成本价/盈亏/警示状态）
    │  3. 组装 System Prompt + 用户输入 + 持仓上下文
    ▼
DataFetcher.get_stock_full_data("600519")
    │  1. TushareAdapter 获取日线/财务/资金流向
    │  2. DataValidator 校验 OHLC、检测停牌
    │  3. QuotaManager 记录调用，接近上限时降级到 AKShare
    │  4. 返回 StockData 对象
    ▼
MasterAgent.LLMCoordinator
    │  1. 将 StockData 注入 Prompt
    │  2. 调用 Claude API（超时 10 秒）
    │  3. Claude 失败 → 降级到 Kimi API
    │  4. 返回结构化分析文本
    ▼
MasterAgent.ComplianceWrapper
    │  1. 扫描禁止词汇（"必涨""目标价""强烈建议"）
    │  2. 前置免责声明
    │  3. 风险分级标记
    ▼
CardBuilder
    │  1. 选择诊股卡片模板
    │  2. 填充变量（价格/涨跌幅/四维度分析/操作建议/持仓信息）
    │  3. SizeGuard 预检（>25KB 触发裁剪）
    ▼
FeishuGateway.CardSender
    │  发送卡片到飞书群聊
    ▼
用户收到交互卡片
```

**预期耗时：** 数据获取 3-5 秒 + LLM 生成 3-5 秒 + 卡片发送 1 秒 = **< 10 秒**

---

### 流 2：每日晨报生成（08:30 定时触发）

```
APScheduler 触发 MorningBriefTask（独立线程）
    │
    ▼
Scheduler.TradeCalendar
    │  判断当日是否开市 → 休市则跳过
    ▼
PortfolioReader
    │  读取 portfolio.md → 获取持仓列表 + 关注板块
    ▼
DataFetcher（并行获取多类数据）
    │  ├─ 全球市场：美股三大指数、A50期指、汇率（AKShare）
    │  ├─ 持仓公告：每只持仓股 overnight 公告（Tushare/Tushare公告接口）
    │  ├─ 板块热点：关注板块涨速、资金流向（AKShare）
    │  └─ 持仓价格：每只持仓股最新价（Tushare/AKShare）
    ▼
DataValidator
    │  校验所有数据合法性，停牌检测
    ▼
红标警示计算
    │  对比成本价与最新价，|涨跌幅| >= 5% 时标记红色警示
    ▼
MasterAgent.LLMCoordinator
    │  1. 组装晨报 Prompt（全球市场摘要 + 持仓事件摘要 + 板块前瞻）
    │  2. 调用 Claude 生成晨报正文
    │  3. 降级到 Kimi 如果 Claude 失败
    ▼
CardBuilder
    │  1. 选择晨报卡片模板
    │  2. 填充变量（全球市场/持仓事件/板块前瞻/红标警示）
    │  3. SizeGuard 预检（晨报内容长，容易超限）
    ▼
FeishuGateway.CardSender
    │  推送晨报卡片到飞书
    ▼
Scheduler.HealthReporter
    │  发送"晨报推送成功"确认消息
```

**预期耗时：** 数据获取 10-15 秒 + LLM 生成 10-20 秒 + 卡片发送 1 秒 = **< 30 秒**

---

### 流 3：持仓读取与同步（每次查询时）

```
MasterAgent.ContextAssembler 触发
    │
    ▼
PortfolioReader 读取 portfolio.md
    │
    ├─ 解析成功 ───────────────────────────────┐
    │                                          ▼
    │                              格式校验（正则）
    │                                          │
    │                              ├─ 通过 ────► SQLite 保存快照
    │                              │            发送确认消息到飞书
    │                              │            返回 Holdings 列表
    │                              │
    │                              └─ 失败 ────► 发送告警卡片到飞书
    │                                             回退到 SQLite 缓存
    │                                             返回缓存的 Holdings
    │
    └─ 文件不存在/读取失败 ────────────────────► 发送告警卡片到飞书
                                                  回退到 SQLite 缓存
                                                  返回缓存的 Holdings
```

---

## 项目目录结构

```
finance-bot/
├── config/
│   ├── __init__.py
│   ├── settings.py           # pydantic-settings: 环境变量加载与类型验证
│   └── .env.example          # 环境变量模板（不含真实密钥）
│
├── core/
│   ├── __init__.py
│   ├── feishu_gateway.py     # FeishuGateway: WebSocket + 消息解析 + 卡片发送
│   ├── master_agent.py       # MasterAgent: 意图路由 + 上下文组装 + LLM 协调
│   └── scheduler.py          # Scheduler: APScheduler 定时任务 + 交易日历
│
├── data/
│   ├── __init__.py
│   ├── fetcher.py            # DataFetcher: 统一数据接口
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── tushare_adapter.py
│   │   ├── akshare_adapter.py
│   │   └── sina_adapter.py
│   ├── validator.py          # DataValidator: OHLC 校验 + 停牌检测
│   └── quota_manager.py      # QuotaManager: Tushare 额度监控
│
├── models/
│   ├── __init__.py
│   ├── schemas.py            # Pydantic 数据模型: StockData, Holding, UserQuery 等
│   └── database.py           # peewee ORM 模型 + 数据库初始化
│
├── cards/
│   ├── __init__.py
│   ├── builder.py            # CardBuilder: 模板渲染 + 大小预检
│   ├── templates.py          # 模板变量定义 + 模板 ID 映射
│   └── size_guard.py         # SizeGuard: 30KB 预检 + 裁剪策略
│
├── portfolio/
│   ├── __init__.py
│   ├── reader.py             # PortfolioReader: MD 解析 + 格式校验
│   └── portfolio.md          # 用户持仓文档（Git 跟踪，方便版本管理）
│
├── llm/
│   ├── __init__.py
│   ├── client.py             # LLMCoordinator: Claude/Kimi 统一封装
│   ├── prompts.py            # 所有 Prompt 模板（诊股/晨报/帮助）
│   └── compliance.py         # ComplianceWrapper: 合规检查 + 免责声明
│
├── utils/
│   ├── __init__.py
│   ├── logger.py             # loguru 配置
│   └── helpers.py            # 通用工具（股票代码规范化、日期处理等）
│
├── tests/
│   ├── __init__.py
│   ├── test_data_fetcher.py
│   ├── test_portfolio_reader.py
│   └── test_card_builder.py
│
├── main.py                   # 应用入口: 初始化所有组件 + 启动 WebSocket + Scheduler
├── requirements.txt
├── README.md
└── finance_bot.db            # SQLite 单文件数据库（.gitignore）
```

---

## 架构模式

### 模式 1：适配器模式（Adapter Pattern）

**用途：** 统一多个异构数据源的接口。

**为什么：** Tushare、AKShare、新浪财经的 API 签名、返回格式、错误处理方式完全不同。适配器模式让 DataFetcher 对外提供单一接口，内部处理所有差异。

```python
from abc import ABC, abstractmethod

class DataSourceAdapter(ABC):
    @abstractmethod
    def get_daily(self, code: str) -> pd.DataFrame:
        pass

class TushareAdapter(DataSourceAdapter):
    def get_daily(self, code: str) -> pd.DataFrame:
        # Tushare 特定实现
        return self.pro.daily(ts_code=code)

class AkshareAdapter(DataSourceAdapter):
    def get_daily(self, code: str) -> pd.DataFrame:
        # AKShare 特定实现
        return ak.stock_zh_a_hist(symbol=code[:6])
```

---

### 模式 2：策略模式（Strategy Pattern）

**用途：** 卡片大小超限时的多种处理策略。

**为什么：** 不同场景下裁剪策略不同（诊股卡片内容固定，晨报卡片内容动态）。策略模式让 SizeGuard 根据场景选择最优策略。

```python
class SizeStrategy(ABC):
    @abstractmethod
    def handle_oversize(self, card: dict, excess_kb: float) -> list[dict]:
        pass

class CollapseStrategy(SizeStrategy):
    """折叠策略：将次要内容放入折叠面板"""
    pass

class SplitStrategy(SizeStrategy):
    """分片策略：拆分为多条消息发送"""
    pass
```

---

### 模式 3：管道模式（Pipeline Pattern）

**用途：** 诊股和晨报的数据处理流程。

**为什么：** 数据获取 → 校验 → 分析 → 合规检查 → 卡片构建，每个步骤的输出是下一个步骤的输入，天然适合管道。

```python
# 诊股管道
pipeline = [
    fetch_stock_data,      # DataFetcher
    validate_data,         # DataValidator
    analyze_with_llm,      # LLMCoordinator
    check_compliance,      # ComplianceWrapper
    build_card,            # CardBuilder
    send_card              # FeishuGateway
]

result = user_query
for step in pipeline:
    result = step(result)
```

---

## 反模式（必须避免）

### 反模式 1：微服务拆分

**错误做法：** 将 FeishuGateway、MasterAgent、DataFetcher 拆分为独立进程/容器，用消息队列通信。

**为什么错：** 个人 Demo 单用户场景，拆分增加部署复杂度、调试难度、网络故障点。

**正确做法：** 所有组件在同一个 Python 进程中运行，通过函数调用通信。

---

### 反模式 2：多 Agent 物理拆分

**错误做法：** TechAgent、FundaAgent、QuantAgent、SentiAgent 作为独立类/进程，各自调用 LLM。

**为什么错：** 4 次 LLM 调用 = 4 倍延迟 + 4 倍成本 + 输出矛盾风险。PITFALLS.md 明确指出 80% 的多 Agent 系统过度工程化。

**正确做法：** 单 Agent + 多维度 Prompt，一个 LLM 调用输出四个维度的分析。

---

### 反模式 3：缓存持仓文档

**错误做法：** 启动时读取 portfolio.md 到内存，后续查询直接使用内存缓存。

**为什么错：** 用户明确要求"机器人每次主动读取更新上下文"，缓存会导致机器人使用过期持仓。

**正确做法：** 每次查询时重新读取 portfolio.md，仅在解析失败时回退到 SQLite 缓存。

---

### 反模式 4：同步阻塞 WebSocket 处理

**错误做法：** 在 WebSocket 消息回调中同步执行数据获取 + LLM 生成，阻塞事件循环。

**为什么错：** 飞书 WebSocket 事件是顺序推送的，同步处理会导致后续消息排队，响应时间不可控。

**正确做法：** 使用 `asyncio` 异步处理消息，数据获取和 LLM 调用使用 `async/await`。

---

## 构建顺序（依赖关系）

基于组件间的依赖关系，建议按以下顺序构建：

```
Phase 1: 基础骨架（可独立验证）
├── 1.1 config/settings.py          # 环境变量配置（无依赖）
├── 1.2 utils/logger.py             # 日志配置（无依赖）
├── 1.3 models/schemas.py           # 数据模型定义（无依赖）
├── 1.4 models/database.py          # SQLite ORM + 建表（依赖 schemas）
└── 1.5 tests/ 基础测试框架

Phase 2: 飞书连接（核心入口）
├── 2.1 core/feishu_gateway.py      # WebSocket 连接 + 消息解析 + 卡片发送
├── 2.2 cards/templates.py          # 卡片模板定义
├── 2.3 cards/size_guard.py         # 大小预检
└── 2.4 验证：机器人能在群聊中响应 @消息

Phase 3: 数据层（核心能力）
├── 3.1 data/adapters/tushare_adapter.py    # Tushare 主数据源
├── 3.2 data/adapters/akshare_adapter.py    # AKShare 备用源
├── 3.3 data/validator.py                   # 数据校验
├── 3.4 data/quota_manager.py               # 额度监控
├── 3.5 data/fetcher.py                     # 统一接口封装
└── 3.6 验证：输入股票代码能获取完整数据

Phase 4: 持仓管理（个性化基础）
├── 4.1 portfolio/portfolio.md      # 定义 MD 格式模板
├── 4.2 portfolio/reader.py         # MD 解析 + 校验 + 回退
└── 4.3 验证：修改 MD 后机器人能读取最新持仓

Phase 5: LLM 层（智能核心）
├── 5.1 llm/client.py               # Claude/Kimi 统一封装
├── 5.2 llm/prompts.py              # 诊股/晨报 Prompt 模板
├── 5.3 llm/compliance.py           # 合规检查 + 免责声明
└── 5.4 验证：输入数据能生成结构化分析文本

Phase 6: 中央调度（业务编排）
├── 6.1 core/master_agent.py        # 意图路由 + 上下文组装 + 流程编排
└── 6.2 验证：@机器人 → 数据获取 → LLM 分析 → 卡片发送 端到端

Phase 7: 卡片构建（用户体验）
├── 7.1 cards/builder.py            # 模板渲染 + 变量填充
└── 7.2 验证：卡片在飞书手机端和 PC 端渲染正常

Phase 8: 定时晨报（自动化）
├── 8.1 core/scheduler.py           # APScheduler + 交易日历 + 晨报任务
└── 8.2 验证：定时触发 → 晨报生成 → 推送成功

Phase 9: 集成与打磨
├── 9.1 main.py                     # 应用入口，组件初始化与启动
├── 9.2 错误处理完善
├── 9.3 日志与监控
└── 9.4 端到端测试
```

**关键依赖关系：**
- FeishuGateway 不依赖任何业务组件（最先构建）
- DataFetcher 不依赖 LLM（可与 LLM 层并行开发）
- MasterAgent 依赖 FeishuGateway、DataFetcher、PortfolioReader、LLM（最后构建）
- Scheduler 依赖 MasterAgent 和 DataFetcher（晨报需要数据和 LLM）

---

## 扩展性考量

本项目定位为个人 Demo，但架构预留了有限的扩展空间：

| 扩展场景 | 当前架构支持度 | 需要做的改动 |
|----------|--------------|-------------|
| 增加第 4/5/6 个晨报模块 | 高 | 修改 `llm/prompts.py` 中的晨报 Prompt，增加数据源调用 |
| 支持港股/美股查询 | 中 | 在 DataFetcher 中增加港股/美股适配器，修改代码规范化逻辑 |
| 卡片交互按钮（查看详情/换一只） | 中 | 增加卡片回调处理路由，FeishuGateway 需处理 `card.action.trigger` 事件 |
| 多用户支持 | 低 | 需要重构 portfolio.md 为按用户隔离，增加用户认证层 |
| 独立 Sub-Agent 拆分 | 低 | 第一期明确不做，如需拆分需重构 MasterAgent 为 Agent 编排器 |
| 历史诊断记录查询 | 高 | SQLite 中已有 `api_calls` 表，增加查询接口即可 |

---

## 关键决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 单进程 vs 多进程 | 单进程 | 个人 Demo，无并发需求，简化部署 |
| 单 Agent vs 多 Agent | 单 Agent + 多维度 Prompt | 降低延迟和成本，避免输出矛盾 |
| 每次读取 MD vs 缓存 | 每次读取 | 用户明确要求，确保上下文最新 |
| 模板 ID vs 手写 JSON | 模板 ID | 飞书卡片搭建工具可视化维护，代码只传变量 |
| APScheduler vs 系统 Cron | APScheduler | Python 原生，与 asyncio 兼容，有持久化和错误处理 |
| 异步 vs 同步 | 异步（asyncio） | WebSocket 事件驱动，避免阻塞 |

---

## 来源

- [飞书开放平台 - 使用长连接接收事件](https://open.feishu.cn/document/server-docs/event-subscription-guide/event-subscription-configure-/request-url-configuration-case) — WebSocket 模式配置，HIGH 置信度
- [飞书开放平台 - 消息卡片搭建工具](https://open.feishu.cn/document/tools-and-resources/message-card-builder) — 模板 ID 使用方式，HIGH 置信度
- [飞书卡片回调交互文档](https://open.feishu.cn/document/feishu-cards/card-callback-communication) — 3 秒响应约束，HIGH 置信度
- [APScheduler 官方文档](https://apscheduler.readthedocs.io/) — BackgroundScheduler 与 asyncio 共存，HIGH 置信度
- [peewee ORM 官方文档](https://docs.peewee-orm.com/) — SQLite 单文件使用模式，HIGH 置信度
- [lark-oapi PyPI](https://pypi.org/project/lark-oapi/) — WebSocket 客户端使用，HIGH 置信度
- [PITFALLS.md 本项目研究](d:\APPuim\自动推送\.planning\research\PITFALLS.md) — 10 个已知陷阱及规避策略，HIGH 置信度
- [STACK.md 本项目研究](d:\APPuim\自动推送\.planning\research\STACK.md) — 技术栈选型及版本，HIGH 置信度
- [FEATURES.md 本项目研究](d:\APPuim\自动推送\.planning\research\FEATURES.md) — 功能依赖关系及 MVP 定义，HIGH 置信度

---
*架构研究：智能金融晨报与交互分析系统*
*研究日期：2026-04-27*
