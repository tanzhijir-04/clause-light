# Task 9: 基本认证中间件实现报告

**状态:** DONE
**日期:** 2026-06-18

## 实现内容

为 ClauseLight 后端添加了基于 API Key 的认证中间件，保护所有 API 端点免受未授权访问。

## 修改文件

### 1. `server/config.py` — 新增 API_KEY 配置项

在 `Settings` 类中添加了 `API_KEY: str = ""` 字段。
- 空字符串（默认值）表示认证关闭，所有请求放行
- 通过环境变量 `API_KEY` 或 `.env` 文件设置后，所有 API 请求必须携带 `X-API-Key` 请求头

### 2. `server/core/auth.py` — 新建认证模块

实现了以下功能：
- **`_is_exempt(path)`** — 判断路径是否免认证（`/`、`/health`、`/api/connection/health`、`/static`、`/admin`、`/mobile`、`/asset`）
- **`verify_api_key(api_key)`** — 验证 API Key，使用 `secrets.compare_digest` 恒定时间比较防止时序攻击
- **`auth_middleware(request, call_next)`** — ASGI 中间件，从 `X-API-Key` 请求头或 `?api_key=` 查询参数获取密钥并验证

### 3. `server/main.py` — 注册认证中间件

在 CORS 中间件之后、请求日志之前注册了 `BaseHTTPMiddleware`，确保：
- 认证在 CORS 之后执行（先处理跨域预检）
- 认证在日志之前执行（未授权请求不会产生日志噪音）

## 行为说明

| 场景 | 行为 |
|------|------|
| `API_KEY` 为空（默认） | 所有请求放行，认证完全关闭 |
| `API_KEY` 已设置，请求携带正确 Key | 放行 |
| `API_KEY` 已设置，请求未携带 Key | 返回 401 |
| `API_KEY` 已设置，请求携带错误 Key | 返回 401 |
| 访问 `/health`、`/static/*`、`/admin/*` 等 | 免认证放行 |

## 验证结果

- `server.config.settings` 加载正常，`API_KEY` 默认为空字符串
- `server.core.auth` 模块导入和逻辑验证通过
- `server.main` 应用导入成功（18 条路由）
- 默认配置下认证关闭，不影响现有功能
