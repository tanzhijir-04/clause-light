# Task 4 实现报告：添加 WebSocket 接口测试

## 完成状态

**DONE** — 所有 23 个测试用例通过，已提交并推送到 GitHub。

## 变更文件

- **新建**: `tests/test_api_ws.py` — 23 个 WebSocket 接口测试用例

## 测试覆盖概览

| 测试类 | 测试数 | 覆盖范围 |
|--------|--------|----------|
| `TestWebSocketConnection` | 6 | 连接建立、ping/pong、元数据、多连接 |
| `TestWebSocketAnalyze` | 8 | 空文本、正常分析、进度回调、Agent失败、风险等级、数据库持久化 |
| `TestWebSocketDisconnect` | 3 | 资源清理、分析后断开、多客户端 |
| `TestWebSocketUnknownMessage` | 5 | 未知类型、无效JSON、缺失字段、额外字段、空type |

## 关键技术决策

### 数据库隔离

`server/api/ws.py` 直接使用 `async_session_factory`（非依赖注入），因此 WS 测试需要：

1. 创建独立的内存 SQLite 数据库（`_ws_test_engine`）
2. 在 fixture 中 patch `server.api.ws.async_session_factory` 指向测试工厂
3. 每个测试前创建表结构，测试后清理

### Mock 策略

- **ContractAgent**: 完整 mock `analyze` 方法，避免 OCR/LLM 调用
- **进度回调**: Mock 的 `analyze` 方法显式调用 `on_step` 回调以验证进度消息
- **唯一 ID**: 使用 `uuid.uuid4().hex` 生成测试 ID 避免数据库约束冲突

### 遇到的问题及解决

1. **UNIQUE constraint failed**: mock 的固定 ID 与数据库残留数据冲突 -> 改用 `uuid.uuid4().hex`
2. **invalid_json 测试挂起**: 无效 JSON 导致连接关闭，`receive_json` 阻塞 -> 改为验证连接清理行为
3. **riskLevel 判断逻辑**: ws.py 中 `red_count > 0` 优先于 `yellow_count` -> 修正断言

## 测试结果

```
23 passed, 1 warning in 1.67s
```

现有 113 个测试未受影响（1 个预存失败与本次无关）。
