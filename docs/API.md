# API 文档

## 合同分析

### POST /api/contracts/analyze
上传合同文件并分析（SSE 流式进度）。

**请求**：
- Content-Type: multipart/form-data
- file: 合同文件（图片/PDF/Office 等）
- contract_type: 可选，指定合同类型

**最终结果事件**（额外字段，旧客户端可忽略）：
- `sessionId`：L0 记忆会话 id

### GET /api/contracts
合同列表。

### GET /api/contracts/{id}
合同详情（含 `sessionId`，若分析时已写入）。

### POST /api/contracts/{id}/feedback
提交反馈。

### WebSocket `/ws`
手机端分析结果 `data.sessionId` 透出记忆会话。

## 知识库

### GET /api/knowledge/rules
规则列表。

### POST /api/knowledge/rules
新增规则。

### GET /api/knowledge/stats
知识库统计。

## 记忆 / Skill / Wiki

### 记忆
| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/api/memory/sessions` | L0 会话 |
| GET | `/api/memory/atoms` | L1 列表/搜索 |
| POST | `/api/memory/feedback` | 用户纠错反馈 |
| GET | `/api/memory/pending` | 待审资产聚合 |
| POST | `/api/memory/pending/{id}/approve` | 审核通过 |
| POST | `/api/memory/pending/{id}/reject` | 拒绝 |
| POST | `/api/memory/pending/{id}/rollback` | 回滚自动上线项 |

### Skill
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/skills` | 列表 |
| POST | `/api/skills` | 创建 |
| GET | `/api/skills/match` | 按合同类型/关键词匹配 |

### Wiki
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/wiki/search` | 关键词搜索 |
| GET | `/api/wiki/{slug}` | 页面详情（可带一跳链接） |
| POST | `/api/wiki/ingest` | 从法规 JSON 冷启动 |

## 同步

### POST /api/sync/push
推送数据。

### POST /api/sync/pull
拉取数据。
