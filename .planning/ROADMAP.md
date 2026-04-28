# Roadmap: 智能金融晨报与交互分析系统

## Overview

从项目骨架到完整飞书金融助手的构建旅程。第一阶段搭建配置、日志、数据模型等基础设施；第二阶段并行建立飞书连接能力和数据获取层，实现机器人在线收发消息和多源金融数据拉取；第三阶段并行开发持仓管理和 LLM 分析能力，让机器人理解用户持仓并具备智能分析大脑；第四阶段将各组件集成为完整的交互系统，实现卡片渲染、中央调度和定时晨报自动化；最终交付一个每天 08:30 自动推送晨报、30 秒内响应诊股查询的个人金融助手。

## Phases

- [x] **Phase 1: 基础骨架** — 配置管理、日志、ORM、数据模型、安全基线
- [x] **Phase 2: 飞书连接与数据层** — WebSocket 机器人接入 + Tushare/AKShare 数据获取
- [x] **Phase 3: 持仓管理与 AI 大脑** — Markdown 持仓解析 + Claude/Kimi 诊股与晨报生成
- [x] **Phase 4: 集成调度与卡片交付** — 中央调度、卡片模板、定时晨报、端到端打通

## Phase Details

### Phase 1: 基础骨架
**Goal**: 项目具备可运行的基础环境、类型安全的配置管理、结构化日志、SQLite 数据模型，所有敏感信息通过环境变量注入
**Depends on**: Nothing (first phase)
**Requirements**: COMP-03
**Success Criteria** (what must be TRUE):
  1. 开发者可以通过 `.env` 文件配置所有 API Key 和连接参数，应用启动时自动校验必填项
  2. 应用运行时产生结构化日志（含时间戳、级别、模块名），自动按天轮转并压缩归档
  3. SQLite 数据库文件自动创建，包含持仓缓存、历史记录、API 调用计数等核心表结构
  4. 所有配置项具备类型校验，缺失必填配置时应用拒绝启动并给出明确错误提示
**Plans**: TBD

### Phase 2: 飞书连接与数据层
**Goal**: 机器人在飞书保持在线，能收发消息和卡片；同时能从 Tushare 和 AKShare 获取行情、全球市场、公告等多维度金融数据，异常时自动降级
**Depends on**: Phase 1
**Requirements**: FEISHU-01, FEISHU-02, FEISHU-03, FEISHU-04, FEISHU-05, DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DELIVERY-04, COMP-01
**Success Criteria** (what must be TRUE):
  1. 用户在飞书群聊中 @机器人，机器人 3 秒内回复"我在"确认在线
  2. 用户输入无效股票代码（如"999999"），机器人返回友好提示："未找到该代码，请检查是否为 A股/港股 有效代码"
  3. 用户输入 A股 6 位代码或港股代码，机器人能正确识别并准备查询
  4. 机器人发送的消息卡片底部固定显示"数据截止 HH:MM"和"AI生成内容仅供参考，不构成投资建议"
  5. 数据获取异常时（Tushare 额度耗尽或接口故障），系统自动切换 AKShare 备用源，用户无感知
**Plans**: 2 plans
**Plan list**:
- [ ] 02-01-PLAN.md — 飞书 WebSocket 连接与消息处理（FEISHU-01~05, DELIVERY-04, COMP-01）
- [ ] 02-02-PLAN.md — 金融数据获取层（DATA-01~05）
**UI hint**: yes

### Phase 3: 持仓管理与 AI 大脑
**Goal**: 机器人能读取用户持仓文档作为分析上下文，具备单 Prompt 多维度诊股和晨报生成的 AI 能力，支持主备模型自动切换
**Depends on**: Phase 2
**Requirements**: PORTFOLIO-01, PORTFOLIO-02, PORTFOLIO-03, PORTFOLIO-04, ANALYSIS-01, ANALYSIS-02, ANALYSIS-03, ANALYSIS-04, ANALYSIS-05, COMP-02
**Success Criteria** (what must be TRUE):
  1. 用户修改 portfolio.md 后，下一次 @机器人诊股时，机器人已使用最新持仓作为分析上下文
  2. 持仓股触发成本价 ±5% 的催化因素时，机器人返回的卡片标题带 🔴 红标警示
  3. portfolio.md 格式损坏时，机器人仍能从 SQLite 缓存读取持仓并告警管理员
  4. 诊股结果包含综合评分 + 一句话策略建议（进攻型/防御型/观望型），附支撑压力位与止损线
  5. Claude 不可用时，诊股和晨报生成自动降级到 Kimi，响应时间仍保持在 15 秒内
  6. AI 分析中所有数值均来自实时 API 数据，LLM 不会编造股价或财务数据
**Plans**: TBD

### Phase 4: 集成调度与卡片交付
**Goal**: 各组件集成为完整系统，用户 @机器人后 30 秒内获得结构化诊股卡片；每日 08:30 自动推送 3 模块晨报；卡片超限自动裁剪，节假日自动跳过
**Depends on**: Phase 3
**Requirements**: DELIVERY-01, DELIVERY-02, DELIVERY-03, SCHED-01, SCHED-02, SCHED-03, SCHED-04
**Success Criteria** (what must be TRUE):
  1. 用户 @机器人输入股票代码后 30 秒内，收到包含 Header、技术速览、多派会诊、操作建议的完整交互卡片
  2. 每日 08:30（仅交易日），飞书群聊自动收到晨报卡片，含隔夜全球市场、持仓重大事件、今日板块前瞻 3 个模块
  3. 周末和法定节假日，晨报不触发，不产生无效推送
  4. 晨报内容超过 25KB 时，自动折叠次要内容并分段发送，不触发飞书卡片大小限制错误
  5. 08:25 若晨报未生成完毕，群聊收到延迟警告卡片，附带"数据截止 08:25"
**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. 基础骨架 | 1/1 | Complete | 2026-04-27 |
| 2. 飞书连接与数据层 | 2/2 | Complete | 2026-04-27 |
| 3. 持仓管理与 AI 大脑 | 1/1 | Complete | 2026-04-27 |
| 4. 集成调度与卡片交付 | 1/1 | Complete | 2026-04-27 |
