# Requirements: 智能金融晨报与交互分析系统

**Defined:** 2026-04-30
**Core Value:** 每天开盘前 3 分钟读完晨报就知道今天该看什么；@机器人 30 秒内知道这只票能不能买。

## v1 Requirements (All Completed — Archived)

See: `.planning/milestones/v1.0-REQUIREMENTS.md`

### v1 交付成果概要

- **飞书机器人**: WebSocket 长连接、A股/港股/中文查询、交互卡片
- **数据获取**: Tushare → AKShare → iTick 三级降级、额度监控、数据校验
- **持仓管理**: portfolio.md 解析、成本价 ±5% 红标警示
- **AI 分析**: Claude Code CLI 四维度诊股、Kimi Agent 网页直出晨报
- **卡片交付**: 智能章节渲染、动态主题色、免责声明
- **定时任务**: 每日 08:30 晨报推送、07:30 数据预准备、03:00 过期清理
- **合规**: 免责声明、数值校验、环境变量注入

## v2 Requirements (Active)

### 晨报增强

- [ ] **SCHED-05**: 晨报扩展至 6 大模块（增加龙虎榜与机构动向、今日关键时间节点、大盘技术位与策略建议）
- [ ] **SCHED-06**: 晨报总字数控制在 1500 字以内，3 分钟内可读完

### 交互增强

- [ ] **DELIVERY-05**: 卡片内添加交互按钮：[查看分时图]、[加入自选]、[深度研报]（占位）
- [ ] **FEISHU-06**: 模糊匹配时提示用户确认（如"茅台"对应 600519，提示"是否查询港股 0852.HK？"）

### 数据增强

- [ ] **DATA-06**: 板块资金流数据获取与板块轮动跟踪
- [ ] **DATA-07**: 舆情热度数据获取（雪球/淘股吧情绪指数）
- [ ] **DATA-08**: 多数据源交叉验证（Tushare + AKShare + 新浪财经）

### 记录与反馈

- [ ] **PORTFOLIO-05**: 历史诊断记录本地 SQLite 存储，支持"查看上次诊断"
- [ ] **ANALYSIS-06**: 用户可标记诊股结果"准/不准"，用于后续 Prompt 优化

## Out of Scope

| Feature | Reason |
|---------|--------|
| 高并发支持（>1 用户同时查询） | 个人 demo，单线程顺序处理即可 |
| Redis 缓存层 | 本地 JSON 缓存已满足需求（v1.0 新增） |
| 复杂数据库架构 | SQLite 单文件即可，零运维 |
| Webhook 部署模式 | 仅 WebSocket，开发最简单 |
| 实时 L2 行情 | 3 分钟延迟数据足够 |
| 独立 Sub-Agent 并行架构 | 第一期串行调用降低复杂度 |
| 股票自动交易执行 | 仅分析建议，不涉及下单 |
| 情绪面新闻爬虫 | 依赖 NLP 和爬虫稳定性，P2 阶段再考虑 |
| 全市场扫描/选股 | 超出个人持仓跟踪范围 |
| 移动端 App / Web 前端 | 飞书卡片即为交互界面 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FEISHU-01~05 | v1.0 | Archived |
| DATA-01~05 | v1.0 | Archived |
| PORTFOLIO-01~04 | v1.0 | Archived |
| ANALYSIS-01~05 | v1.0 | Archived |
| DELIVERY-01~04 | v1.0 | Archived |
| SCHED-01~04 | v1.0 | Archived |
| COMP-01~03 | v1.0 | Archived |
| SCHED-05~06 | v2 | Active |
| DELIVERY-05 | v2 | Active |
| FEISHU-06 | v2 | Active |
| DATA-06~08 | v2 | Active |
| PORTFOLIO-05 | v2 | Active |
| ANALYSIS-06 | v2 | Active |

**Coverage:**
- v1 requirements: 29 total — All archived
- v2 requirements: 9 total — All active
- Unmapped: 0

---
*Requirements defined: 2026-04-30*
*Last updated: 2026-04-30 after Phase 5 Kimi Agent completion*
