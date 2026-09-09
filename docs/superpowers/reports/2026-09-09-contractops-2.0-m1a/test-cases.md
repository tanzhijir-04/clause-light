# ContractOps 2.0 M1-A 测试用例清单

## 执行范围

- 执行日期：2026-09-09
- Python：3.12.5
- 平台：Windows
- 数据库：SQLite；正式摄取回归使用 pytest 临时数据库
- 外部服务：未启动 Docker、PostgreSQL、Redis 或远端向量服务
- M1-A 专项用例：25 个

## M1-A 专项用例

- [`tests/v2/test_rag_models.py`](../../../../tests/v2/test_rag_models.py)：知识文档/Chunk 表结构、唯一约束和元数据字段。
- [`tests/v2/test_rag_chunking.py`](../../../../tests/v2/test_rag_chunking.py)：文本规范化、分块边界、来源标签、主题标签和原文位置。
- [`tests/v2/test_rag_ingest.py`](../../../../tests/v2/test_rag_ingest.py)：法规/规则 JSON 校验、幂等摄取、版本停用和坏输入拒绝。
- [`tests/v2/test_rag_retriever.py`](../../../../tests/v2/test_rag_retriever.py)：SQLite 词法检索、ACL 过滤、字符预算、引用和降级模式。
- [`tests/v2/test_rag_conflicts.py`](../../../../tests/v2/test_rag_conflicts.py)：显式 `conflict_key` 冲突、权威级别排序和人工复核标记。
- [`tests/v2/test_rag_evaluation.py`](../../../../tests/v2/test_rag_evaluation.py)：固定评测集、Recall@5/10、MRR@10、重复命中和 ACL 泄漏指标。
- [`tests/v2/test_rag_ingest_cli.py`](../../../../tests/v2/test_rag_ingest_cli.py)：CLI 参数、dry-run 只读计数、Alembic 后正式摄取和重复摄取幂等。

## 回归范围

- `tests/v2/`：M0 + M1-A 回归，共 52 个用例。
- `tests/`、`tests/v2/`、`tests/integration/`：全项目回归，共 398 个收集用例，最终 393 passed、5 skipped。
