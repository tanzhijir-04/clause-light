# ContractOps 2.0 M0 测试用例清单

## 执行信息

- 执行日期：2026-09-09
- Python：3.12.5
- 测试框架：pytest
- 用例收集命令：`python -m pytest --collect-only -q --override-ini addopts=`
- 实际收集：373 个用例
- 完整执行命令：`python -m pytest -q`

## M0 新增与重点用例

### 基础设施与配置

- [tests/v2/test_settings.py](../../../../tests/v2/test_settings.py)：生产配置必须使用 PostgreSQL/Redis，测试环境允许 SQLite。
- [tests/v2/test_database_platform.py](../../../../tests/v2/test_database_platform.py)：数据库 session 的提交与回滚。
- [tests/v2/test_foundation_models.py](../../../../tests/v2/test_foundation_models.py)：基础表和幂等约束。

### 合同、版本与接口

- [tests/v2/test_contract_service.py](../../../../tests/v2/test_contract_service.py)：重复幂等请求不重复创建合同和任务。
- [tests/v2/test_contract_api.py](../../../../tests/v2/test_contract_api.py)：创建合同、缺少幂等键、合同与版本查询。
- [tests/v2/test_tenant_isolation.py](../../../../tests/v2/test_tenant_isolation.py)：不同组织之间的数据隔离。

### 任务与事件

- [tests/v2/test_job_repository.py](../../../../tests/v2/test_job_repository.py)：过期租约回收、步骤幂等完成。
- [tests/v2/test_job_recovery.py](../../../../tests/v2/test_job_recovery.py)：可重试 Worker 失败后回到队列。
- [tests/v2/test_job_api.py](../../../../tests/v2/test_job_api.py)：任务查询、取消和事件列表。

### 认证、审计与隐私

- [tests/v2/test_tenant_auth.py](../../../../tests/v2/test_tenant_auth.py)：API Key 摘要、统一未授权响应、有效租户上下文。
- [tests/v2/test_audit_redaction.py](../../../../tests/v2/test_audit_redaction.py)：敏感字段脱敏后再持久化。
- [tests/v2/test_log_privacy.py](../../../../tests/v2/test_log_privacy.py)：合同正文不进入日志。
- [tests/v2/test_observability.py](../../../../tests/v2/test_observability.py)：Request ID 和有界 metrics route label。

### Redis、导入与 OCR

- [tests/v2/test_rate_limit.py](../../../../tests/v2/test_rate_limit.py)：进程内限流窗口。
- [tests/v2/test_progress_fallback.py](../../../../tests/v2/test_progress_fallback.py)：Redis 不可用时进度降级且不丢最终状态。
- [tests/v2/test_legacy_importer.py](../../../../tests/v2/test_legacy_importer.py)：dry-run 和重复导入。
- [tests/v2/test_legacy_import_idempotency.py](../../../../tests/v2/test_legacy_import_idempotency.py)：坏外键报告不包含合同正文。
- [tests/integration/test_ocr_runtime.py](../../../../tests/integration/test_ocr_runtime.py)：固定 PaddleOCR 运行时读取真实中文合同图片。

## 原有回归范围

- `tests/test_*.py`：ClauseLight v1 API、OCR、解析、Agent、LLM、知识库、记忆、WebSocket 和 Worker 回归。
- `tests/v2/`：ContractOps M0 单元及 API 测试。
- `tests/integration/`：Docker M0、PostgreSQL、Redis 和 OCR 集成入口。

pytest 的结果输出摘要见同目录的 `pytest-output.txt`；本清单中的测试源码即为实际执行的测试用例来源。
