# Phase 4 总结：集成调度与卡片交付

## 完成内容

### 新增文件

| 文件 | 说明 |
|------|------|
| `src/core/models.py` | 新增 `MorningReportRecord` 表 |
| `src/core/database.py` | 初始化包含晨报记录表 |
| `src/scheduler/__init__.py` | 模块导出 |
| `src/scheduler/jobs.py` | APScheduler 定时任务管理 |
| `src/cards/__init__.py` | 模块导出 |
| `src/cards/diagnosis_card.py` | 诊股卡片渲染（飞书 Card JSON 2.0） |
| `src/cards/morning_report_card.py` | 晨报卡片渲染 |
| `src/orchestrator.py` | 中央调度器：消息→分析→卡片→发送 |
| `tests/test_scheduler.py` | 调度器测试 |
| `tests/test_cards.py` | 卡片渲染测试 |
| `tests/test_orchestrator.py` | 中央调度器测试 |

### 关键实现

- **SchedulerManager**: APScheduler 后台调度，每日 08:30 触发晨报推送，凌晨 03:00 自动清理 7 天前的晨报记录。支持手动触发（`trigger_now`）。
- **DiagnosisCardBuilder**: 根据诊股结果构建飞书卡片，Header 颜色对应策略（进攻=红/防御=橙/观望=蓝），持仓警示显示 🔴 红标，包含评分、策略、支撑压力位、止损线、分析正文。
- **MorningReportCardBuilder**: 晨报卡片渲染，支持延迟警告卡片。
- **BotOrchestrator**: 完整交互链路：飞书消息 → MessageParser 解析 → DiagnosisAnalyzer 分析 → CardBuilder 渲染 → CardSender 发送。同时处理晨报生成和推送，保存诊断历史和晨报记录。

### 用户定制需求

- **每日推送（不按交易日）**: `SCHED-02` 已修改为每日执行，周末和节假日不跳过。
- **晨报保留 7 天**: `MorningReportRecord` 表记录每次晨报，凌晨 3 点自动清理超过 7 天的记录。

### 测试覆盖

- `test_scheduler.py`: 4 个测试，覆盖启动/停止、手动触发、7 天清理、自定义时间
- `test_cards.py`: 8 个测试，覆盖诊股卡片成功/警示/观望/错误/无价，晨报成功/空内容/延迟警告
- `test_orchestrator.py`: 6 个测试，覆盖消息处理/无效输入/非文本/@机器人空内容/晨报发送/延迟警告

**测试结果**: 18 passed, 0 failed（项目总计 92 passed）
