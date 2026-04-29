# 智能金融晨报与交互分析系统

## What This Is

一套基于飞书平台的个人智能金融助手，具备两大核心能力：每日开盘前（08:30）自动推送个性化金融晨报；用户在飞书群内 @机器人输入股票代码，实时获取当日详情与交易建议。面向 A股/港股短线投资者的个人 demo 使用。

## Core Value

每天开盘前 3 分钟读完晨报就知道今天该看什么；@机器人 30 秒内知道这只票能不能买。

## Requirements

### Validated

- 每日 08:30 定时推送个性化金融晨报（飞书消息卡片） — v1.0
- 晨报包含：隔夜全球市场速览、持仓个股重大事件、今日重点板块前瞻 — v1.0
- 飞书 @机器人交互，支持 A股 6 位代码 / 港股代码 / 中文简称查询 — v1.0
- 个股诊断返回飞书交互卡片，含技术速览 + 多 Agent 会诊 + 操作建议 — v1.0
- 内置持仓 MD 文档，机器人每次读取作为上下文进行智能分析 — v1.0
- 持仓股有 overnight 公告时，红标警示（成本价 ±5% 触发） — v1.0
- Kimi Agent 网页直出晨报，Playwright 自动化提取完整 Markdown — v1.0 Phase 5
- 飞书卡片智能章节渲染，一级/二级标题差异化样式 + 情绪评级动态主题色 — v1.0 Phase 5

### Active

- [ ] 晨报扩展至 6 大模块（增加龙虎榜与机构动向、今日关键时间节点、大盘技术位与策略建议）
- [ ] 晨报总字数控制在 1500 字以内
- [ ] 卡片内添加交互按钮：[查看分时图]、[加入自选]、[深度研报]（占位）
- [ ] 模糊匹配时提示用户确认（如"茅台"对应 600519，提示"是否查询港股 0852.HK？"）
- [ ] 板块资金流数据获取与板块轮动跟踪
- [ ] 舆情热度数据获取（雪球/淘股吧情绪指数）
- [ ] 多数据源交叉验证（Tushare + AKShare + 新浪财经）
- [ ] 历史诊断记录本地 SQLite 存储，支持"查看上次诊断"
- [ ] 用户可标记诊股结果"准/不准"，用于后续 Prompt 优化

### Out of Scope

- **高并发支持** — 个人 demo，单线程顺序处理即可
- **Redis 缓存层** — 本地 JSON 缓存已满足需求（v1.0 新增）
- **复杂数据库架构** — SQLite 单文件即可，零运维
- **Webhook 部署模式** — 仅 WebSocket，开发最简单
- **实时 L2 行情** — 3 分钟延迟数据足够
- **独立 Sub-Agent 并行架构** — 第一期串行调用降低复杂度
- **股票交易执行** — 仅分析建议，不涉及下单

## Context

- 用户为个人短线投资者，跟踪半导体、AI 算力、液冷、商业航天等板块
- 持仓以 MD 文档维护，机器人每次主动读取更新上下文
- 数据优先使用 Tushare（免费额度）+ AKShare + iTick 三级降级
- AI 文本生成：Kimi Agent 网页为主引擎，Claude Code CLI (`claude -p`) 为降级备用
- v1.0 已交付：5 个阶段，~4000 行 Python，100+ 测试全通，5 天开发周期（2026-04-25 → 2026-04-30）
- 当前持仓：002709 天赐材料（成本 52.8）

## Constraints

- **Tech stack**: Python，SQLite，飞书 WebSocket 机器人
- **Budget**: 优先使用免费数据 API，控制 LLM 调用成本
- **Timeline**: 个人 demo，优先跑通核心流程再迭代
- **Performance**: 诊股响应 < 15 秒，晨报生成 < 30 分钟
- **Compliance**: 每条消息底部固定添加"AI生成内容仅供参考，不构成投资建议"

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python 技术栈 | 用户熟悉，金融数据生态丰富 | Adopted |
| 持仓用 MD 文档管理 | 简单可编辑，机器人每次读取更新上下文 | Adopted |
| Claude Code CLI (`claude -p`) 为 LLM 后端 | 利用本地已安装的 Claude Code CLI，无需额外 API Key | Adopted |
| WebSocket 单模式部署 | 无需公网 IP，开发最简单 | Adopted |
| SQLite 替代 Redis+分表 | 个人 demo 零运维 | Adopted |
| 本地 JSON 缓存 + iTick 备用源 | 减少 API 调用、提升响应速度；iTick 免费版作为第 3 级降级 | Adopted |
| 每日推送晨报（不按交易日） | 用户要求每日执行，周末和法定节假日不跳过 | Adopted |
| 中文名称通过持仓匹配代码 | 用户输入中文简称时，从 portfolio.md 匹配对应代码 | Adopted |
| 三级数据降级（Tushare → AKShare → iTick） | 确保数据获取高可用，用户无感知切换 | Adopted |
| Kimi Agent 作为晨报生成主引擎 | Kimi 联网搜索能力更强，晨报内容更丰富；Claude CLI 保留为降级备用 | Adopted |
| 固定等待 7 分钟策略 | 替代纯轮询检测，确保 Kimi 思考过程滚动完毕后再提取内容 | Adopted |
| 文本提取去污染（坐标+思考过滤） | 去除 Kimi 网页中的坐标标记和思考过程，确保输出纯净 Markdown | Adopted |
| 飞书卡片章节拆分渲染 | 一级/二级标题差异化样式，提升可读性 | Adopted |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-30 after v1.0 milestone (Phase 5 Kimi Agent complete)*
