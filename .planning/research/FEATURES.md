# Feature Research: 智能金融晨报与交互分析系统

**Domain:** 个人智能金融助手（A股/港股短线投资）
**Researched:** 2026-04-25
**Confidence:** MEDIUM（基于WebSearch生态调研+PROJECT.md上下文，未进行用户访谈验证）

---

## Feature Landscape

### Table Stakes（用户预期必备，缺失则产品不可用）

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **每日定时晨报推送** | 核心承诺：每天08:30自动推送 | LOW | APScheduler定时任务即可，飞书WebSocket长连接保持在线 |
| **隔夜全球市场速览** | 短线投资者开盘前必看：美股、A50期指、汇率 | LOW | AKShare免费接口可获取美股指数、汇率；Tushare免费版仅A股日线 |
| **持仓个股公告监控** | 持仓股overnight公告直接影响开盘决策 | MEDIUM | 需对接公告数据源（东方财富/新浪财经爬虫），MD持仓文档解析 |
| **个股代码查询响应** | @机器人输入代码30秒内返回结果 | LOW | 飞书@消息监听→代码解析→数据查询→卡片返回，串行流程<15秒 |
| **AI免责声明** | 合规底线，每条消息底部固定添加 | LOW | 卡片模板固定footer即可 |
| **A股6位代码/港股代码/中文简称识别** | 用户查询的自然输入方式 | LOW | 正则匹配+AKShare名称模糊查询 |

### Differentiators（竞争优势，个人Demo的亮点）

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **多Agent会诊诊股卡片** | 技术+基本面+资金面+情绪面四维AI分析，非单一指标罗列 | MEDIUM | 串行调用4个分析prompt，Claude生成综合结论；第一期可简化为单prompt多维度 |
| **持仓成本价±5%红标警示** | 个人化风控，公告+价格双重触发 | LOW | MD文档中解析成本价，与当前价对比；红色高亮飞书卡片 |
| **飞书交互卡片（非纯文本）** | 信息密度高、视觉层次清晰、支持按钮交互 | MEDIUM | 需设计卡片模板（header+分栏+折叠详情+action按钮），飞书卡片builder可视化搭建 |
| **今日重点板块前瞻** | 结合用户持仓板块+市场热点，个性化推荐 | MEDIUM | 需维护板块-个股映射表，AKShare获取板块涨速数据 |
| **Markdown持仓文档智能读取** | 零数据库运维，纯文本可编辑，机器人每次读取更新 | LOW | Python frontmatter解析MD文件，提取持仓列表+成本价+关注板块 |
| **操作建议（观望/关注/减仓/加仓）** | 从"数据展示"升级为"决策辅助" | MEDIUM | LLM基于多维度分析生成明确操作建议，需精心设计prompt避免误导 |

### Anti-Features（个人Demo应明确不做）

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **实时L2行情推送** | 专业投资者觉得3分钟延迟不够 | Tushare L2收费¥1000/月，AKShare无L2；个人Demo日频足够 | 使用15分钟延迟免费数据，标注"数据延迟15分钟" |
| **自动交易执行** | 想实现"分析→下单"闭环 | 涉及券商API接入、合规风险、资金安全，远超Demo范围 | 明确仅提供分析建议，交易决策由用户自主执行 |
| **Redis缓存层** | 担心频繁调用API限流 | 个人Demo单用户，内存dict缓存足够；引入Redis增加部署复杂度 | Python内置LRU缓存（functools.lru_cache）或简单dict |
| **独立Sub-Agent并行架构** | 追求技术先进性 | 并行增加调试难度，个人Demo串行调用足够；Claude API本身有速率限制 | 第一期串行，第二期视性能需求再考虑并发 |
| **多用户/权限管理** | 想扩展给朋友圈使用 | 个人Demo定位明确为单人使用；多用户引入数据库设计、权限隔离 | 硬编码单用户，后续如需扩展再重构 |
| **历史回测/策略验证** | 想验证AI建议的准确率 | 需要大量历史数据存储和回测框架，与Demo核心目标（晨报+诊股）偏离 | 手动记录建议，人工复盘；如需量化回测另起项目 |
| **全市场扫描/选股** | 想发现新的交易机会 | 全市场5000+股票分析，API调用量和LLM成本爆炸 | 聚焦持仓股+用户主动查询，控制成本 |
| **Webhook部署模式** | 觉得WebSocket不够"正式" | WebSocket无需公网IP、无需配置回调URL，开发最简单；Webhook需服务器+域名 | 坚持WebSocket单模式，降低部署门槛 |

---

## Feature Dependencies

```
[飞书机器人基础连接]
    └──requires──> [消息监听与响应]
        └──requires──> [股票代码解析]
            ├──requires──> [个股数据查询]
            │   └──requires──> [AKShare/Tushare数据源]
            └──requires──> [LLM分析生成]
                └──requires──> [Claude/Kimi API配置]

[Markdown持仓文档]
    ├──requires──> [持仓解析模块]
    │   └──enhances──> [持仓公告监控]
    │       └──requires──> [公告数据源]
    └──enhances──> [个股诊股上下文]
        └──enhances──> [诊股卡片个性化]

[飞书交互卡片模板]
    ├──requires──> [卡片Builder设计]
    └──requires──> [卡片回调处理]
        └──requires──> [3秒内响应机制]

[每日定时晨报]
    ├──requires──> [定时任务调度]
    ├──requires──> [全球市场数据]
    ├──requires──> [板块热点数据]
    ├──requires──> [持仓公告扫描]
    └──requires──> [LLM内容生成]
        └──requires──> [晨报卡片模板]

[多Agent会诊]
    ├──conflicts──> [响应时间<15秒]
    │   └──mitigation──> [第一期简化为单Prompt多维度]
    └──requires──> [个股全维度数据]
        ├──requires──> [技术面数据]
        ├──requires──> [基本面数据]
        ├──requires──> [资金面数据]
        └──requires──> [情绪面/新闻数据]
```

### Dependency Notes

- **诊股响应时间 vs 多Agent会诊存在冲突**：4个Agent串行调用Claude API，每次2-3秒，总耗时可能超过15秒目标。第一期建议合并为单Prompt要求LLM输出多维度分析，将复杂度从HIGH降至MEDIUM。
- **持仓文档是多个功能的增强器**：不阻塞核心功能，但有了持仓数据后，晨报和诊股都能提供个性化内容。
- **卡片回调需要3秒内响应**：飞书平台硬性要求，复杂分析必须异步处理，先返回"分析中"卡片，再推送结果卡片。

---

## MVP Definition

### Launch With（v1）—— 验证核心概念

- [ ] **飞书机器人基础连接** — 能接收@消息、能发送文本/卡片消息
- [ ] **个股代码查询响应** — 输入"600519"或"贵州茅台"，返回基础行情卡片（现价、涨跌幅、成交量）
- [ ] **单Prompt AI诊股** — 技术+基本面+资金面+情绪面四维分析，单LLM调用生成，返回结构化卡片
- [ ] **每日定时晨报（3模块）** — 隔夜全球市场+持仓公告摘要+今日板块前瞻，08:30推送
- [ ] **Markdown持仓读取** — 解析MD文档，诊股时识别"持仓股"标签，晨报中关联持仓板块
- [ ] **成本价±5%红标警示** — 持仓股公告+价格触发时，卡片中红色高亮显示

### Add After Validation（v1.x）—— 核心跑通后迭代

- [ ] **晨报模块扩展至6个** — 增加龙虎榜、关键事件日历、技术支撑位（数据可用时）
- [ ] **卡片交互按钮** — "查看详情"、"换一只股票"、"加入关注"等按钮回调
- [ ] **诊股多Agent拆分** — 验证单用户场景下串行/并行性能，再决定是否拆分独立Agent
- [ ] **历史诊断记录** — SQLite本地存储，支持"查看上次诊断"

### Future Consideration（v2+）—— 产品市场匹配后

- [ ] **多数据源融合** — AKShare+Tushare+新浪财经交叉验证，提高数据可靠性
- [ ] **情绪面新闻爬虫** — 财联社/华尔街见闻关键词抓取，NLP情绪分析
- [ ] **板块轮动跟踪** — 长期记录板块热度变化，生成轮动周期判断
- [ ] **诊股结果反馈学习** — 用户标记"准/不准"，微调prompt或建立简单评分模型

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| 飞书机器人基础连接 | HIGH | LOW | P1 |
| 个股代码查询响应 | HIGH | LOW | P1 |
| 单Prompt AI诊股 | HIGH | MEDIUM | P1 |
| 每日定时晨报（3模块） | HIGH | MEDIUM | P1 |
| Markdown持仓读取 | MEDIUM | LOW | P1 |
| 成本价±5%红标警示 | MEDIUM | LOW | P1 |
| 飞书交互卡片模板 | MEDIUM | MEDIUM | P1 |
| 晨报扩展至6模块 | MEDIUM | MEDIUM | P2 |
| 卡片交互按钮 | MEDIUM | MEDIUM | P2 |
| 诊股多Agent拆分 | LOW | HIGH | P2 |
| 历史诊断记录 | LOW | LOW | P2 |
| 情绪面新闻爬虫 | MEDIUM | HIGH | P3 |
| 板块轮动跟踪 | LOW | HIGH | P3 |
| 多数据源融合 | LOW | MEDIUM | P3 |
| 诊股反馈学习 | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch（缺失则Demo无法演示核心流程）
- P2: Should have, add when core is working（增强体验，但不阻塞核心）
- P3: Nice to have, future consideration（个人Demo阶段过度设计）

---

## Competitor Feature Analysis

| Feature | 同花顺i问财 | 东方财富妙想 | 九方灵犀 | 随牛AI | Our Approach |
|---------|------------|-------------|----------|--------|--------------|
| 每日晨报推送 | APP推送，通用模板 | 无 | 无 | 无 | **飞书定时卡片，个性化持仓关联** |
| 个股诊股维度 | 四维（基/技/资/消） | 查询+研报 | 长短期+量化因子 | 30+维度 | **单Prompt四维+操作建议** |
| 交互方式 | APP内搜索 | APP内对话 | APP内报告 | 网页报告 | **飞书@机器人，30秒响应** |
| 持仓关联 | 需登录绑定账户 | 需登录 | 需登录 | 无 | **MD文档零门槛管理** |
| 数据成本 | 免费（广告变现） | 免费 | 付费订阅 | 付费 | **免费API+LLM按量，个人可控** |
| 部署复杂度 | SaaS，零部署 | SaaS，零部署 | SaaS，零部署 | SaaS，零部署 | **本地Python脚本，WebSocket直连** |

**差异化定位：**
- 同花顺/东方财富是"超级APP内的功能模块"，我们是"个人专属、飞书原生、零门槛部署"的独立助手
- 商业产品追求覆盖全市场、全用户，我们追求"持仓关联的个性化"和"决策辅助的明确性"
- MD持仓管理是独特设计：无需注册、无需同步券商账户、纯文本可版本控制

---

## Sources

- [Tushare官方文档 - 积分与频次权限](https://tushare.pro/document/1?doc_id=290) — Tushare免费版限制确认
- [AKShare vs Tushare对比分析](https://blog.infoway.io/tushare-akshare-infoway-api-comparison/) — 数据源选型参考
- [飞书卡片回传交互回调文档](https://open.feishu.cn/document/feishu-cards/card-callback-communication?lang=zh-CN) — 卡片交互技术约束
- [飞书按钮组件文档](https://open.feishu.cn/document/feishu-cards/feishu-card-cardkit/components/button?lang=zh-CN) — 按钮回调机制
- [随牛AI智能诊股功能解析](https://mtz.china.com/touzi/2026/0128/215391.html) — 商业AI诊股维度参考
- [AI投资助手功能详解](https://www.myinvestpilot.com/docs/ai-assistant/capabilities) — 多维度分析框架
- [StockAnal_Sys GitHub项目](https://github.com/LargeCupPanda/StockAnal_Sys) — 开源多维度股票分析实现
- [A股短线投资者学习路线](https://www.cnblogs.com/cy-xt/p/18711031) — 短线投资者信息需求
- [飞书AI机器人流式输出实践](https://blog.csdn.net/qq_34846662/article/details/157552376) — 飞书卡片更新最佳实践
- [每日财经数据自动抓取+飞书推送](https://blog.csdn.net/fzil001/article/details/160259467) — 类似项目功能参考
- [量化实战：从0到1搭建简单量化系统](https://learn.lianglianglee.com/) — 个人Demo范围控制参考

---
*Feature research for: 智能金融晨报与交互分析系统*
*Researched: 2026-04-25*
