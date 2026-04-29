# Phase 5 Plan 01 总结：Kimi Agent 网页直出晨报

## 完成内容

### 新增文件

| 文件 | 说明 |
|------|------|
| `src/llm/kimi_agent_browser.py` | Playwright 自动化访问 Kimi Agent 网页，固定等待 7 分钟后提取完整 Markdown 晨报 |
| `src/llm/kimi_report_prompt.py` | Kimi 超级 Prompt，注入全球市场数据、持仓个股新闻、关注板块 |
| `src/data/kimi_adapter.py` | MD 格式校验与清洗：坐标过滤、思考过程过滤、prompt 前 100 字符排除 |
| `data/kimi_cookies.json` | Kimi 登录 Cookie 持久化存储 |

### 改造文件

| 文件 | 改造内容 |
|------|----------|
| `src/analysis/morning_report.py` | 晨报生成器：支持 Kimi Agent 和 Claude CLI 双引擎切换 |
| `src/scheduler/jobs.py` | 定时任务：07:30 数据预准备 → 07:35 Kimi 生成（20min 超时） |
| `src/orchestrator.py` | 中央调度器：支持 `--source kimi/claude` 参数触发 |
| `src/core/models.py` | 数据库模型：新增 `KimiRawData` 表存储原始回复 |
| `src/cards/morning_report_card.py` | 飞书卡片渲染：章节拆分，一级/二级标题差异化样式，制表符表格转 Markdown |
| `config/settings.py` | 配置管理：新增 Kimi 相关配置项 |
| `.env` | 环境变量：新增 Kimi 相关配置 |
| `requirements.txt` | 新增 playwright 依赖 |

### 关键实现

- **Kimi Agent 网页自动化**: Playwright 打开 https://www.kimi.com/agent，注入超级 Prompt（含全球市场数据、持仓新闻、关注板块），固定等待 7 分钟确保思考过程滚动完毕后提取完整 Markdown 内容
- **文本去污染**: 坐标过滤（去除 `[思考中...]` 等坐标标记）、思考过程关键词过滤、prompt 前 100 字符排除
- **双引擎架构**: Kimi Agent 为主引擎，Claude Code CLI 为降级备用，通过 `--source` 参数切换
- **智能飞书卡片**: 章节拆分渲染，一级标题 blue + heading + emoji，二级标题 grey + normal，制表符表格自动转 Markdown 表格，情绪评级动态主题色
- **数据流时序**: 07:30 数据预准备（~30-60 秒）→ 07:35 Kimi 生成（20 分钟超时）→ 本地后处理 → SQLite 入库 → 飞书发送

### 验收结果

- Kimi Agent 端到端链路验证通过
- 飞书卡片格式优化完成
- 降级路径（Kimi 超时/异常 → Claude CLI）可用
