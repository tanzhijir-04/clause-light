# 代码审查修复报告

## 修复概览

本次修复了代码审查发现的 6 类问题，其中 2 个关键问题、4 个重要问题。

**Commit**: `64e0fa34` — `fix: 修复代码审查发现的 6 类问题`

---

## 关键修复

### 1. 认证中间件阻断 WebSocket 连接

**文件**: `server/core/auth.py`

**问题**: 当 `API_KEY` 被设置时，`/ws/client` 路径未被豁免认证。WebSocket 连接以 HTTP 升级请求形式发起，会经过认证中间件拦截，导致手机端无法建立 WebSocket 连接。

**修复**: 在 `_EXEMPT_PREFIXES` 中添加 `/ws` 前缀，所有 WebSocket 路径免认证。

```python
# 修复前
_EXEMPT_PREFIXES = ("/static", "/admin", "/mobile", "/asset")

# 修复后
_EXEMPT_PREFIXES = ("/static", "/mobile", "/asset", "/ws")
```

### 2. 自动学习类别映射使用错误字段

**文件**: `server/core/knowledge.py`

**问题**: `trigger_auto_learning` 方法使用 `clause.risk_type` 映射规则类别，但 `risk_type` 存储的是风险描述（如"违约金过高"），不是合同类型。`TYPE_CATEGORY_MAP` 的键是合同类型（如"租赁合同"），导致映射永远失败，规则类别始终为"通用"。

**修复**: 通过 `ClauseAnalysis.analysis_id` -> `Analysis.contract_id` -> `Contract.type` 关联查询父合同类型，再使用 `TYPE_CATEGORY_MAP` 正确映射规则类别。

```python
# 修复前
category = TYPE_CATEGORY_MAP.get(clause.risk_type, "通用") if clause.risk_type else "通用"

# 修复后：通过 Analysis -> Contract 获取合同类型
category = "通用"
if clause.analysis_id:
    analysis_stmt = select(Analysis).where(Analysis.id == clause.analysis_id)
    analysis_result = await self.db.execute(analysis_stmt)
    analysis = analysis_result.scalar_one_or_none()
    if analysis and analysis.contract_id:
        contract_stmt = select(Contract).where(Contract.id == analysis.contract_id)
        contract_result = await self.db.execute(contract_stmt)
        contract = contract_result.scalar_one_or_none()
        if contract and contract.type:
            category = TYPE_CATEGORY_MAP.get(contract.type, "通用")
```

### 3. WebSocket 外层异常处理器未通知客户端

**文件**: `server/api/ws.py`

**问题**: 当异常发生在 `analyze` 的 `try/except` 块之外（如消息解析失败），客户端收不到任何错误消息，导致无限等待。

**修复**: 在外层 `except Exception` 中添加 `send_json` 通知客户端连接异常。

```python
except Exception as e:
    logger.error("WebSocket 错误: %s", e)
    try:
        await websocket.send_json({
            "type": "error",
            "message": f"连接异常: {e}",
            "code": "CONNECTION_ERROR",
        })
    except Exception:
        pass
```

### 4. 移除不存在的 /admin 路径豁免

**文件**: `server/core/auth.py`

**问题**: `_EXEMPT_PREFIXES` 中包含 `/admin`，但代码库中不存在管理面板，该豁免无实际用途且存在安全隐患。

**修复**: 从 `_EXEMPT_PREFIXES` 中移除 `/admin`。

---

## 新增测试

### 5. 合同删除 API 测试

**文件**: `tests/test_api_contracts.py` — `TestDeleteContract` 类（5 个测试）

| 测试 | 说明 |
|------|------|
| `test_delete_existing_contract` | 删除存在的合同，验证 200 和数据库清理 |
| `test_delete_nonexistent_contract` | 删除不存在的合同，验证 404 |
| `test_delete_cascade_analysis_and_clauses` | 验证级联删除 Analysis 和 ClauseAnalysis |
| `test_delete_source_file_cleanup` | 验证上传的源文件被清理 |
| `test_delete_missing_source_file_no_error` | 源文件不存在时不报错 |

### 6. 反馈到知识库管道测试

**文件**: `tests/test_api_contracts.py` — 1 个集成测试
- `test_submit_feedback_incorrect_triggers_auto_learning`：验证 incorrect 反馈端到端触发自动学习

**文件**: `tests/test_knowledge.py` — `TestTriggerAutoLearning` 类（7 个测试）

| 测试 | 说明 |
|------|------|
| `test_auto_learning_creates_rule` | 从反馈创建新规则，验证类别映射为"租赁" |
| `test_auto_learning_empty_content_skips` | 空条款内容跳过学习 |
| `test_auto_learning_whitespace_content_skips` | 纯空白内容跳过学习 |
| `test_auto_learning_duplicate_skips` | 重复规则跳过学习 |
| `test_auto_learning_category_from_contract_type` | 劳动合同映射为"劳动"类别 |
| `test_auto_learning_no_analysis_fallback` | 无关联分析时使用"通用"类别 |
| `test_auto_learning_unknown_contract_type` | 未知合同类型使用"通用"类别 |

---

## 测试结果

```
188 passed, 1 failed (pre-existing: test_list_devices — /api/devices 端点未实现)
```

所有新增测试通过，原有测试无回归。
