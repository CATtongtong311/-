# Phase 6: 交互增强与记录反馈 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-30
**Phase:** 06-interaction-feedback
**Areas discussed:** 模糊匹配确认机制, 卡片交互按钮实现, 诊股反馈标记方式

---

## 模糊匹配确认机制

| Option | Description | Selected |
|--------|-------------|----------|
| 全市场映射表 | 本地缓存所有 A股+港股名称映射，支持任意股票查询，定期自动更新 | ✓ |
| 在线查询兜底 | portfolio 无匹配时调用 AKShare 接口实时查询，有延迟但维护简单 | |
| 多候选提示+选择 | 匹配到多结果时回复候选列表，用户回复数字选择 | (子策略，与映射表配合) |

**User's choice:** 全市场映射表
**Notes:** 多候选提示作为映射表的补充策略——当映射表返回多结果时，以候选列表形式提示用户选择。

---

## 卡片交互按钮实现

| Option | Description | Selected |
|--------|-------------|----------|
| 按钮 + WebSocket 回调 | 在 gateway 中增加 card.action.trigger 事件处理 | ✓ |
| 文本指令替代 | 用户回复文本指令触发功能 | |
| 按钮占位（纯展示） | 卡片上显示按钮样式但无回调 | |

**User's choice:** 按钮 + WebSocket 回调
**Notes:** 按钮功能先做 [查看分时图] 和 [加入自选]，[深度研报] 作为预留。

---

## 诊股反馈标记方式

| Option | Description | Selected |
|--------|-------------|----------|
| 卡片底部按钮 | 诊股卡片底部添加 [准] [不准] 按钮 | |
| 文本指令反馈 | 用户回复"准 002709"或"不准 002709" | |
| 延迟反馈提示 | 诊股3天后自动发送评价提示 | ✓ |
| 卡片按钮 + 延迟提示 | 即时按钮 + N天后汇总验证 | |

**User's choice:** 延迟反馈提示
**Notes:** 3 天后自动发送"请评价上次诊股"提示，用户回复"准"或"不准"。反馈记录用于后续 Prompt 优化。

---

## Claude's Discretion

- **历史诊断查询方式** — 未在本次讨论中确定，由下游规划 agent 决定具体实现。

## Deferred Ideas

- 按钮功能 [深度研报] 需要额外数据源支持，超出 Phase 6 范围
- 历史诊断可视化（评分趋势图表）
