# 技术栈研究

**项目:** 智能金融晨报与交互分析系统
**领域:** 个人金融助手 / 飞书机器人
**研究日期:** 2026-04-25
**置信度:** HIGH

## 推荐技术栈

### 核心框架

| 技术 | 版本 | 用途 | 推荐理由 |
|------|------|------|----------|
| Python | 3.11+ | 运行时 | 金融数据生态最丰富，Tushare/AKShare均原生支持，asyncio成熟 |
| lark-oapi | 1.5.5 | 飞书机器人SDK | 官方维护，支持WebSocket长连接（无需公网IP），自动处理token刷新和重连 |
| APScheduler | 3.11.2 | 定时任务调度 | Python定时任务标准方案，cron表达式支持完善，BackgroundScheduler适合与WebSocket共存 |

### 数据层

| 技术 | 版本 | 用途 | 推荐理由 |
|------|------|------|----------|
| tushare | 1.4.29 | A股基础数据（主） | 免费版覆盖日线/财务/基本面数据，DataFrame输出，积分制但个人用量足够 |
| akshare | 1.18.11 | 备用数据源 | 完全免费无需注册，东方财富/新浪双源，Tushare故障时自动降级 |
| peewee | 3.19.0 | SQLite ORM | 轻量级ORM，单文件零配置，API直观，性能接近SQLAlchemy但代码量少50% |
| python-frontmatter | 1.1.0 | 持仓MD文件解析 | Jekyll风格YAML frontmatter解析，读写一体，持仓文件即配置即数据 |

### AI/LLM层

| 技术 | 版本 | 用途 | 推荐理由 |
|------|------|------|----------|
| anthropic | 0.97.0 | Claude API调用 | 官方SDK，支持streaming、tool use、完整类型提示，Claude分析质量公认最高 |
| openai | 1.99+ | Kimi API调用 | Moonshot API完全兼容OpenAI格式，复用同一SDK减少依赖，base_url切换即可 |

### 基础设施

| 技术 | 版本 | 用途 | 推荐理由 |
|------|------|------|----------|
| pydantic-settings | 2.14.0 | 配置管理 | 内置.env加载+类型验证，替代python-dotenv+手动校验，2025年Python配置管理标准 |
| loguru | 0.7.3 | 日志记录 | 零配置开箱即用，自动文件轮转/压缩，异常捕获装饰器，个人项目生产力首选 |
| httpx | 0.28.1 | HTTP客户端 | 同步/异步双模式，HTTP/2支持，类型注解完整，requests的现代替代 |

### 开发工具

| 工具 | 用途 | 备注 |
|------|------|------|
| ruff | 代码格式化和lint | 替代flake8+black+isort，Rust编写极快 |
| mypy | 静态类型检查 | 配合Pydantic提供完整类型安全 |

## 安装命令

```bash
# 核心依赖
pip install lark-oapi==1.5.5
pip install apscheduler==3.11.2

# 数据层
pip install tushare
pip install akshare
pip install peewee==3.19.0
pip install python-frontmatter==1.1.0

# AI层
pip install anthropic
pip install openai

# 基础设施
pip install pydantic-settings==2.14.0
pip install loguru==0.7.3
pip install httpx==0.28.1

# 开发依赖
pip install ruff mypy
```

## 替代方案对比

| 类别 | 推荐方案 | 替代方案 | 何时使用替代 |
|------|----------|----------|-------------|
| 飞书SDK | lark-oapi | 自建HTTP封装 | 仅当官方SDK不满足特殊需求时 |
| 定时任务 | APScheduler | schedule | schedule极简但无持久化，APScheduler更适合长期运行 |
| 数据源 | Tushare+AKShare | Baostock/efinance | Baostock免注册但数据更新慢，efinance分钟级但历史短 |
| ORM | peewee | SQLAlchemy 2.0 | SQLAlchemy功能最全但学习曲线陡峭，复杂多表关联时考虑 |
| 配置管理 | pydantic-settings | python-dotenv | 旧项目迁移时保留dotenv，新项目直接用pydantic-settings |
| HTTP客户端 | httpx | requests | requests生态更广，但httpx的async支持是未来趋势 |

## 明确不推荐

| 避免使用 | 原因 | 替代方案 |
|----------|------|----------|
| Redis | 个人demo无需缓存层，内存dict足够，引入Redis增加部署复杂度 | Python内置dict + 必要时sqlite缓存表 |
| Celery | 分布式任务队列对个人demo过度设计，APScheduler单进程足够 | APScheduler BackgroundScheduler |
| PostgreSQL/MySQL | 个人demo零运维优先，SQLite单文件即可 | SQLite + peewee |
| Django/FastAPI | Web框架对本项目无用，机器人是长连接客户端非服务端 | 纯Python脚本 + APScheduler |
| LangChain | 增加抽象层但本场景只需直接API调用，过度封装 | 直接调用anthropic/openai SDK |
| 自建Webhook服务 | 需要公网IP或内网穿透，WebSocket模式开发最简单 | lark-oapi WebSocket模式 |
| 飞书旧版卡片JSON 1.0 | 不再更新新属性，新版2.0能力更强 | Card JSON 2.0 (schema: "2.0") |

## 个人Demo约束下的特殊考量

### 为什么单线程足够
- 飞书WebSocket事件是顺序推送的，SDK内部已做队列处理
- 每日晨报是单一cron任务，无并发场景
- 诊股响应<15秒要求可通过异步IO（httpx async）满足，无需多线程

### 为什么SQLite足够
- 仅需存储：用户配置、API调用日志、持仓历史快照
- 数据量预估：<10MB/年
- peewee的SqliteDatabase零配置，单文件可备份

### 为什么内存缓存足够
- 行情数据3分钟延迟，无需实时缓存
- 持仓MD文件每次读取（用户要求），无缓存需求
- LLM响应直接返回，不缓存

### Claude + Kimi 双模型策略

```python
# 统一封装示例
from anthropic import Anthropic
from openai import OpenAI
import os

class LLMClient:
    def __init__(self):
        self.claude = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.kimi = OpenAI(
            api_key=os.getenv("MOONSHOT_API_KEY"),
            base_url="https://api.moonshot.cn/v1"
        )
    
    def analyze(self, prompt: str, use_kimi: bool = False) -> str:
        if not use_kimi:
            try:
                resp = self.claude.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=2048,
                    messages=[{"role": "user", "content": prompt}]
                )
                return resp.content[0].text
            except Exception:
                pass  # 降级到Kimi
        
        resp = self.kimi.chat.completions.create(
            model="kimi-k2-0711-preview",
            messages=[{"role": "user", "content": prompt}]
        )
        return resp.choices[0].message.content
```

### 飞书消息卡片构建策略

推荐使用**卡片搭建工具可视化编辑 + 模板ID发送**，而非手写JSON：

1. 在 [飞书卡片搭建工具](https://open.feishu.cn/cardkit) 可视化设计卡片
2. 发布获取 `template_id`
3. Python代码中仅传入变量：

```python
# 推荐：模板方式（维护简单）
card_data = {
    "type": "template",
    "data": {
        "template_id": "ctp_xxxxxxxx",
        "template_variable": {
            "stock_name": "贵州茅台",
            "price": "1688.88",
            "change": "+2.35%"
        }
    }
}

# 不推荐：手写完整JSON（维护困难）
# 仅在模板不满足时使用
```

## 版本兼容性

| 包A | 兼容包B | 备注 |
|-----|---------|------|
| lark-oapi 1.5.5 | Python 3.7+ | 官方要求 |
| APScheduler 3.11.2 | Python 3.8+ | 稳定版，v4.0alpha不建议生产使用 |
| pydantic-settings 2.14.0 | pydantic 2.7+ | 自动安装依赖 |
| anthropic 0.97.0 | httpx | SDK内部依赖 |
| openai 1.99+ | httpx | SDK内部依赖 |
| peewee 3.19.0 | Python 3.6+ | 稳定维护 |

## 来源

- [lark-oapi PyPI](https://pypi.org/project/lark-oapi/) — 版本1.5.5，HIGH置信度
- [APScheduler PyPI](https://pypi.org/project/APScheduler/) — 版本3.11.2，HIGH置信度
- [anthropic PyPI](https://pypi.org/project/anthropic/) — 版本0.97.0，HIGH置信度
- [pydantic-settings PyPI](https://pypi.org/project/pydantic-settings/) — 版本2.14.0，HIGH置信度
- [peewee 官方文档](https://docs.peewee-orm.com/) — 版本3.19.0，HIGH置信度
- [AKShare 官方文档](https://akshare.akfamily.xyz/) — 版本1.18.11，HIGH置信度
- [Tushare 官方文档](https://tushare.pro/document/3?doc_id=302) — 免费版接口说明，HIGH置信度
- [飞书开放平台 - 消息卡片搭建工具](https://open.feishu.cn/document/tools-and-resources/message-card-builder) — JSON 2.0结构，HIGH置信度
- [飞书开放平台 - 使用长连接接收事件](https://open.feishu.cn/document/server-docs/event-subscription-guide/event-subscription-configure-/request-url-configuration-case) — WebSocket模式配置，HIGH置信度
- [Kimi API 官方文档](https://platform.moonshot.cn/docs/api/overview) — OpenAI兼容格式，HIGH置信度
- [HTTPX 官方文档](https://www.python-httpx.org/) — 版本0.28.1，HIGH置信度
- [Loguru GitHub](https://github.com/Delgan/loguru) — 版本0.7.3，HIGH置信度
- [python-frontmatter PyPI](https://pypi.org/project/python-frontmatter/) — 版本1.1.0，HIGH置信度

---
*技术栈研究：智能金融晨报与交互分析系统*
*研究日期：2026-04-25*
