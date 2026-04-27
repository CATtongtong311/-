# Phase 2 Plan 01 总结：飞书连接层

## 完成内容

### 新增文件

| 文件 | 说明 |
|------|------|
| `src/feishu/__init__.py` | 模块导出 |
| `src/feishu/gateway.py` | WebSocket 网关，基于 lark-oapi ws.Client |
| `src/feishu/message_parser.py` | 消息解析：@提取、A股/港股/中文简称识别 |
| `src/feishu/card_sender.py` | 卡片发送器，大小预检 (>25KB 告警) |
| `src/feishu/disclaimer.py` | 免责声明和数据截止时间注入 |
| `tests/test_message_parser.py` | 消息解析器单元测试 |
| `tests/test_feishu_gateway.py` | 网关/发送器单元测试 |

### 关键实现

- **FeishuGateway**: 使用 lark-oapi `ws.Client` + `EventDispatcherHandler`，支持 `im.message.receive_v1` 事件。外层包装指数退避重连（1s, 2s, 4s, ..., 60s 封顶，最多 10 次）。
- **MessageParser**: 正则提取 A股 6 位代码（前缀 0/3/6 校验）、港股 `.HK` 代码（不区分大小写）、中文简称 2-6 字。去除 @机器人标记。
- **CardSender**: 懒加载 lark-oapi HTTP client，发送前自动注入免责声明，计算卡片大小并预警。
- **inject_footer**: 深拷贝卡片，追加数据截止时间（HH:MM）和 AI 免责声明。

### 测试覆盖

- `test_message_parser.py`: 11 个测试用例，覆盖 A股、港股、中文、无效代码、空消息、无 @ 场景
- `test_feishu_gateway.py`: 12 个测试用例，覆盖卡片构建、footer 注入、大小预警、网关生命周期、消息提取

**测试结果**: 23 passed, 0 failed
