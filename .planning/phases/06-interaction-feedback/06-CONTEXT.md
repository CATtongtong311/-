# Phase 6: 交互增强与记录反馈 - Context

**Gathered:** 2026-04-30
**Status:** Ready for planning

<domain>
## Phase Boundary

在 v1.0 飞书机器人 + 诊股/晨报基础上，增强用户交互体验和记录反馈能力：
- 模糊匹配时提示用户确认（FEISHU-06）
- 卡片内添加交互按钮（DELIVERY-05）
- 历史诊断记录本地 SQLite 存储与查询（PORTFOLIO-05）
- 用户标记诊股结果"准/不准"（ANALYSIS-06）

</domain>

<decisions>
## Implementation Decisions

### 模糊匹配确认机制
- **D-01:** 采用**全市场映射表**方案。本地缓存所有 A股+港股名称映射（JSON/数据库），支持任意股票查询（不限于 portfolio）。映射表定期自动更新（如每周一次或按需）。
- **D-02:** 当用户输入中文简称匹配到多结果时，飞书回复候选列表，用户回复数字或再次输入确认。

### 卡片交互按钮实现
- **D-03:** 采用**按钮 + WebSocket 回调**方案。在 `gateway.py` 中增加 `card.action.trigger` 事件处理，点击按钮触发操作（如查看分时图、加入自选、深度研报）。
- **D-04:** 按钮功能先做 [查看分时图] 和 [加入自选]（占位），[深度研报] 作为预留。

### 诊股反馈标记方式
- **D-05:** 采用**延迟反馈提示**方案。诊股 3 天后（或 configurable），APScheduler 自动发送"请评价上次诊股"的提示消息，用户回复"准"或"不准"。
- **D-06:** 反馈记录到数据库，用于后续 Prompt 优化（如调整诊股策略权重）。

### Claude's Discretion
- **历史诊断查询方式** — 未在本次讨论中确定。建议实现为：用户发送"历史 002709"或"上次诊断 002709"命令，机器人从 `DiagnosisHistory` 表中查询最近 N 次记录，以卡片形式展示。

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 需求与规范
- `.planning/REQUIREMENTS.md` — v2 Active 需求（FEISHU-06, DELIVERY-05, PORTFOLIO-05, ANALYSIS-06）
- `.planning/PROJECT.md` — 项目上下文与约束

### 现有代码
- `src/feishu/message_parser.py` — 当前消息解析逻辑（A股/港股/中文简称）
- `src/feishu/gateway.py` — WebSocket 连接与事件处理（需增加 card.action.trigger）
- `src/feishu/card_sender.py` — 卡片发送接口
- `src/core/models.py` — 数据模型（DiagnosisHistory 已存在，需新增 Feedback 相关）
- `src/cards/diagnosis_card.py` — 诊股卡片结构
- `src/scheduler/jobs.py` — 定时任务调度
- `src/orchestrator.py` — 中央调度器

### 飞书文档
- 飞书 Interactive Card 按钮回调文档（card.action.trigger 事件）

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `MessageParser` (`src/feishu/message_parser.py`) — 可扩展中文简称匹配逻辑，增加全市场映射表查询
- `DiagnosisHistory` 模型 (`src/core/models.py`) — 已存在，可直接用于历史记录存储和查询
- `CardSender` (`src/feishu/card_sender.py`) — 可复用发送反馈提示卡片
- `APScheduler` (`src/scheduler/jobs.py`) — 可复用设置延迟反馈定时任务

### Established Patterns
- WebSocket 事件处理：目前只处理 `im.message.receive_v1`，需要扩展处理 `card.action.trigger`
- 卡片构建：使用 dict 构建飞书 Interactive Card，然后 JSON 序列化发送
- 定时任务：使用 `BackgroundScheduler`，任务函数在 `jobs.py` 中定义

### Integration Points
- 模糊匹配：在 `MessageParser.parse()` 中，中文简称匹配后增加全市场映射表查询
- 卡片按钮：在 `gateway.py` 的 `on_message` 或新事件处理器中处理按钮点击
- 延迟反馈：在 `orchestrator.py` 的诊股完成后，记录到 DiagnosisHistory 并调度 3 天后反馈任务
- 历史查询：新增命令解析逻辑（如"历史"、"上次诊断"前缀）

</code_context>

<specifics>
## Specific Ideas

- 全市场映射表更新策略：首次启动时拉取全部 A股+港股列表，保存到 `data/stock_map.json`，每周自动更新或手动触发更新
- 延迟反馈时机： configurable，默认 3 个交易日（非自然日），避开周末和节假日
- 按钮点击后的响应：暂时用文本消息回复（如"已加入自选"），后续可扩展为卡片更新

</specifics>

<deferred>
## Deferred Ideas

- 按钮功能扩展：[深度研报] 需要额外数据源支持，超出 Phase 6 范围
- 历史诊断可视化：图表展示评分趋势，可在 Phase 8 或后续考虑

</deferred>

---

*Phase: 06-interaction-feedback*
*Context gathered: 2026-04-30*
