# Requirements: 智能金融晨报与交互分析系统

**Defined:** 2026-04-27
**Core Value:** 每天开盘前 3 分钟读完晨报就知道今天该看什么；@机器人 30 秒内知道这只票能不能买。

## v1 Requirements

### 飞书机器人 (FEISHU)

- [x] **FEISHU-01**: 机器人通过 WebSocket 长连接接入飞书，保持在线状态，断线后自动重连
- [x] **FEISHU-02**: 接收群聊和单聊中 @机器人的消息
- [x] **FEISHU-03**: 解析用户输入，支持 A股 6 位数字代码、港股 5 位代码 + .HK、中文简称模糊匹配
- [x] **FEISHU-04**: 向飞书发送 Interactive Card（消息卡片），支持标题颜色区分
- [x] **FEISHU-05**: 无效代码输入时返回友好错误提示："未找到该代码，请检查是否为 A股/港股 有效代码"

### 数据获取 (DATA)

- [x] **DATA-01**: 通过 Tushare 获取 A 股实时行情（3 分钟延迟）：开盘价、最高/最低、当前价、成交量、换手率
- [x] **DATA-02**: 通过 AKShare 作为备用数据源，Tushare 故障或额度耗尽时自动降级切换
- [x] **DATA-03**: 获取隔夜全球市场数据：美股三大指数、纳斯达克中国金龙指数、恒生期货、美元指数、离岸人民币、10Y 美债收益率
- [x] **DATA-04**: 获取持仓个股相关公告和新闻（业绩预告、增减持、大宗交易）
- [x] **DATA-05**: 数据校验层：检测停牌、空值、异常价格，数据异常时标记并降级处理

### 持仓管理 (PORTFOLIO)

- [x] **PORTFOLIO-01**: 每次用户查询时读取 portfolio.md，获取用户持仓列表和上下文
- [x] **PORTFOLIO-02**: 解析持仓成本价、持仓数量、关注板块、备注信息
- [x] **PORTFOLIO-03**: 持仓股触发成本价 ±5% 的催化因素时，在卡片标题加 🔴 红标警示
- [x] **PORTFOLIO-04**: portfolio.md 解析失败时回退到 SQLite 缓存并告警

### AI 分析 (ANALYSIS)

- [x] **ANALYSIS-01**: 单 Prompt 多维度诊股：技术面（K线形态/均线/量能）+ 基本面（财报/公告/政策）+ 资金面（龙虎榜/北向/主力流向）+ 情绪面（题材热度/连板梯队）
- [x] **ANALYSIS-02**: 生成晨报内容，首期覆盖 3 个模块：隔夜全球市场速览、持仓个股重大事件、今日重点板块前瞻
- [x] **ANALYSIS-03**: 诊股输出综合评分 + 一句话策略建议（进攻型/防御型/观望型），附具体支撑压力位与止损线
- [x] **ANALYSIS-04**: 使用 Claude Code CLI 进行诊股分析和晨报生成（已从 Kimi API 切换）
- [x] **ANALYSIS-05**: 所有分析基于实时获取的数据注入 Prompt，禁止 LLM 编造数据；数据缺失时回答"数据暂不可用"

### 卡片构建与交付 (DELIVERY)

- [x] **DELIVERY-01**: 诊股卡片包含 4 个区块：Header（股票名称+代码+当前价+涨跌幅）、技术速览、多派会诊结论、操作建议
- [x] **DELIVERY-02**: 晨报卡片包含 3 个模块内容，结构化分栏展示
- [x] **DELIVERY-03**: 卡片大小预检，超过 25KB 自动触发裁剪策略（折叠次要内容、分段发送）
- [x] **DELIVERY-04**: 每张卡片底部固定显示"数据截止 HH:MM"和"AI生成内容仅供参考，不构成投资建议"

### 定时任务 (SCHED)

- [x] **SCHED-01**: 每日 08:30 自动触发晨报生成和推送到飞书群聊
- [x] **SCHED-02**: 每日执行，周末和法定节假日不跳过（用户要求每天推送晨报）
- [x] **SCHED-03**: 每晚 19:00 预拉取数据，预留时间给 AI 处理与生成
- [x] **SCHED-04**: 08:25 若晨报未生成完毕，发送延迟警告卡片并附带"数据截止 08:25"

### 合规与安全 (COMP)

- [x] **COMP-01**: 每条 AI 生成的消息底部固定添加免责声明："AI生成内容仅供参考，不构成投资建议"
- [x] **COMP-02**: LLM 输出数值与原始数据源比对校验，偏差超过阈值时标记告警
- [x] **COMP-03**: 所有 API Key、App Secret 通过环境变量注入，禁止硬编码

## v2 Requirements

### 晨报增强

- **SCHED-05**: 晨报扩展至 6 大模块（增加龙虎榜与机构动向、今日关键时间节点、大盘技术位与策略建议）
- **SCHED-06**: 晨报总字数控制在 1500 字以内，3 分钟内可读完

### 交互增强

- **DELIVERY-05**: 卡片内添加交互按钮：[查看分时图]、[加入自选]、[深度研报]（占位）
- **FEISHU-06**: 模糊匹配时提示用户确认（如"茅台"对应 600519，提示"是否查询港股 0852.HK？"）

### 数据增强

- **DATA-06**: 板块资金流数据获取与板块轮动跟踪
- **DATA-07**: 舆情热度数据获取（雪球/淘股吧情绪指数）
- **DATA-08**: 多数据源交叉验证（Tushare + AKShare + 新浪财经）

### 记录与反馈

- **PORTFOLIO-05**: 历史诊断记录本地 SQLite 存储，支持"查看上次诊断"
- **ANALYSIS-06**: 用户可标记诊股结果"准/不准"，用于后续 Prompt 优化

## Out of Scope

| Feature | Reason |
|---------|--------|
| 高并发支持（>1 用户同时查询） | 个人 demo，单线程顺序处理即可 |
| Redis 缓存层 | 内存 dict 缓存足够，简化部署 |
| PostgreSQL / MySQL | SQLite 单文件零运维 |
| Webhook 部署模式 | 仅 WebSocket，开发最简单 |
| 实时 L2 行情 | 3 分钟延迟数据足够个人决策 |
| 独立 Sub-Agent 并行架构 | 第一期单 Prompt 多维度分析降低复杂度 |
| 股票自动交易执行 | 仅分析建议，不涉及下单 |
| 情绪面新闻爬虫 | 依赖 NLP 和爬虫稳定性，P2 阶段再考虑 |
| 全市场扫描/选股 | 超出个人持仓跟踪范围 |
| 移动端 App / Web 前端 | 飞书卡片即为交互界面 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FEISHU-01 | Phase 2 | Complete |
| FEISHU-02 | Phase 2 | Complete |
| FEISHU-03 | Phase 2 | Complete |
| FEISHU-04 | Phase 2 | Complete |
| FEISHU-05 | Phase 2 | Complete |
| DATA-01 | Phase 2 | Complete |
| DATA-02 | Phase 2 | Complete |
| DATA-03 | Phase 2 | Complete |
| DATA-04 | Phase 2 | Complete |
| DATA-05 | Phase 2 | Complete |
| PORTFOLIO-01 | Phase 3 | Complete |
| PORTFOLIO-02 | Phase 3 | Complete |
| PORTFOLIO-03 | Phase 3 | Complete |
| PORTFOLIO-04 | Phase 3 | Complete |
| ANALYSIS-01 | Phase 3 | Complete |
| ANALYSIS-02 | Phase 3 | Complete |
| ANALYSIS-03 | Phase 3 | Complete |
| ANALYSIS-04 | Phase 3 | Complete |
| ANALYSIS-05 | Phase 3 | Complete |
| DELIVERY-01 | Phase 4 | Complete |
| DELIVERY-02 | Phase 4 | Complete |
| DELIVERY-03 | Phase 4 | Complete |
| DELIVERY-04 | Phase 2 | Complete |
| SCHED-01 | Phase 4 | Complete |
| SCHED-02 | Phase 4 | Complete |
| SCHED-03 | Phase 4 | Complete |
| SCHED-04 | Phase 4 | Complete |
| COMP-01 | Phase 2 | Complete |
| COMP-02 | Phase 3 | Complete |
| COMP-03 | Phase 1 | Complete |

**Coverage:**
- v1 requirements: 29 total
- Mapped to phases: 29
- Unmapped: 0

---
*Requirements defined: 2026-04-27*
*Last updated: 2026-04-27 after roadmap creation*
