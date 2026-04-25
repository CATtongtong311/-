# 智能金融晨报与交互分析系统

## What This Is

一套基于飞书平台的个人智能金融助手，具备两大核心能力：每日开盘前（08:30）自动推送个性化金融晨报；用户在飞书群内 @机器人输入股票代码，实时获取当日详情与交易建议。面向 A股/港股短线投资者的个人 demo 使用。

## Core Value

每天开盘前 3 分钟读完晨报就知道今天该看什么；@机器人 30 秒内知道这只票能不能买。

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] 每日 08:30 定时推送个性化金融晨报（飞书消息卡片）
- [ ] 晨报包含：隔夜全球市场速览、持仓个股重大事件、今日重点板块前瞻
- [ ] 飞书 @机器人交互，支持 A股 6 位代码 / 港股代码 / 中文简称查询
- [ ] 个股诊断返回飞书交互卡片，含技术速览 + 多 Agent 会诊 + 操作建议
- [ ] 内置持仓 MD 文档，机器人每次读取作为上下文进行智能分析
- [ ] 持仓股有 overnight 公告时，红标警示（成本价 ±5% 触发）

### Out of Scope

- **高并发支持** — 个人 demo，单线程顺序处理即可
- **Redis 缓存层** — 内存 dict 缓存足够，简化部署
- **复杂数据库架构** — SQLite 单文件即可，零运维
- **Webhook 部署模式** — 仅 WebSocket，开发最简单
- **全部 6 个晨报模块** — 第一期先做 3 个核心模块
- **实时 L2 行情** — 3 分钟延迟数据足够
- **独立 Sub-Agent 并行架构** — 第一期串行调用降低复杂度
- **股票交易执行** — 仅分析建议，不涉及下单

## Context

- 用户为个人短线投资者，跟踪半导体、AI 算力、液冷、商业航天等板块
- 持仓以 MD 文档维护，机器人每次主动读取更新上下文
- 数据优先使用 Tushare（免费额度）+ 新浪财经等免费接口
- AI 文本生成以 Claude 为主模型，Kimi API 作为备选

## Constraints

- **Tech stack**: Python，SQLite，飞书 WebSocket 机器人
- **Budget**: 优先使用免费数据 API，控制 LLM 调用成本
- **Timeline**: 个人 demo，优先跑通核心流程再迭代
- **Performance**: 诊股响应 < 15 秒，晨报生成 < 30 分钟
- **Compliance**: 每条消息底部固定添加"AI生成内容仅供参考，不构成投资建议"

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python 技术栈 | 用户熟悉，金融数据生态丰富 | — Pending |
| 持仓用 MD 文档管理 | 简单可编辑，机器人每次读取更新上下文 | — Pending |
| Claude 为主 + Kimi 备选 | Claude 分析质量高，Kimi 成本低可兜底 | — Pending |
| WebSocket 单模式部署 | 无需公网 IP，开发最简单 | — Pending |
| SQLite 替代 Redis+分表 | 个人 demo 零运维 | — Pending |

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
*Last updated: 2026-04-25 after initialization*
