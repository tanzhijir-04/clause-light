# API 文档

## 合同分析

### POST /api/contracts/analyze
上传合同文件并分析。

**请求**：
- Content-Type: multipart/form-data
- file: 合同文件（图片/PDF）
- contract_type: 可选，指定合同类型

**响应**：
```json
{
  "contract_id": "xxx",
  "contract_type": "租赁合同",
  "overall_score": 72,
  "recommendation": "negotiate_first",
  "summary": "存在3处高风险条款",
  "clauses": [...]
}
```

### GET /api/contracts
合同列表。

### GET /api/contracts/{id}
合同详情。

### POST /api/contracts/{id}/feedback
提交反馈。

## 知识库

### GET /api/knowledge/rules
规则列表。

### POST /api/knowledge/rules
新增规则。

### GET /api/knowledge/stats
知识库统计。

## 同步

### POST /api/sync/push
推送数据。

### POST /api/sync/pull
拉取数据。
