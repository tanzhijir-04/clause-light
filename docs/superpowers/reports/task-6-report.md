# Task 6 Report: 添加 Connection API 测试

## 状态: DONE

## 完成内容

创建了 `tests/test_api_connection.py`，为 Connection API 的三个端点添加了 12 个测试用例，全部通过。

### 测试覆盖

| 端点 | 用例数 | 说明 |
|------|--------|------|
| GET /api/connection/info | 3 | 字段完整性、端口一致性、URL 格式 |
| GET /api/connection/health | 5 | 状态码、uptime、连接数、时间戳格式 |
| GET /api/connection/devices | 4 | 空列表、单设备、多设备、字段完整性 |

### 测试策略

- 使用 conftest.py 中的 async `client` fixture（httpx AsyncClient + ASGITransport）
- 对 `server.api.ws.active_connections` 和 `server.api.ws.connection_info` 使用 `unittest.mock.patch` 模拟 WebSocket 状态，确保测试独立性
- 无需真实 WebSocket 连接或数据库数据

### 文件

- 创建: `tests/test_api_connection.py`（190 行）
- 提交: `564c65dc` (已推送至 GitHub)
