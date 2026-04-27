# Phase 2 Plan 02 总结：数据获取层

## 完成内容

### 新增文件

| 文件 | 说明 |
|------|------|
| `src/data/__init__.py` | 模块导出 |
| `src/data/quota.py` | Tushare 额度监控与降级触发 |
| `src/data/validator.py` | 停牌/空值/异常价格校验 |
| `src/data/tushare_adapter.py` | Tushare Pro 主数据源封装 |
| `src/data/akshare_adapter.py` | AKShare 备用数据源封装 |
| `src/data/fetcher.py` | 统一数据获取接口，自动降级 |
| `tests/test_data_validator.py` | 额度管理与数据校验测试 |
| `tests/test_data_fetcher.py` | 数据获取器测试 |

### 关键实现

- **QuotaManager**: 基于 `ApiCallLog` 模型记录每日调用，提供 `remaining()`、`should_fallback()`（剩余 < 20 或错误率 > 50% 时触发降级）。
- **DataValidator**: `validate_quote()` 检测停牌（volume=0/None）、空值（OHLC 任一缺失）、异常价格（涨跌幅 > 20%）。`validate_market_data()` 简化校验关键字段。
- **TushareAdapter**: 封装 `ts.pro_api(token)`，支持 A股/港股行情、全球市场、个股新闻。调用前后与 QuotaManager 交互。所有异常捕获并返回空结构。
- **AkshareAdapter**: 封装 `akshare`，提供与 TushareAdapter 完全一致的标准化返回结构。每个接口单独 try/except，失败不中断流程。
- **DataFetcher**: 统一对外接口。`get_stock_quote` / `get_global_market` / `get_news` 均优先 Tushare，失败/异常/额度不足时自动降级到 AKShare，用户无感知。双源失败返回带警告的失败对象。

### 测试覆盖

- `test_data_validator.py`: 18 个测试用例，覆盖额度初始化、消耗、低额度降级、高错误率降级、正常数据/停牌/空值/NaN/异常价格/全球市场校验
- `test_data_fetcher.py`: 10 个测试用例，覆盖 Tushare 成功、Tushare 失败降级 AKShare、双源失败、停牌降级、全球市场、新闻获取

**测试结果**: 28 passed, 0 failed（Phase 2 总计 51 passed）
