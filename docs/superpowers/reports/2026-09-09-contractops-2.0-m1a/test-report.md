# ContractOps 2.0 M1-A 测试报告

## 结论

通过。M1-A 专项测试 **25 passed**；全项目回归 **393 passed, 5 skipped, 9 warnings**。Ruff 静态检查通过，Alembic 当前 head 为 `20260909_0002`。

## 本阶段验证内容

| 验证项 | 结果 |
|---|---:|
| 模型、迁移和约束 | 通过 |
| 来源规范化、分块和位置追踪 | 通过 |
| 法规/规则幂等摄取和版本保留 | 通过 |
| SQLite 词法检索、ACL 和引用 | 通过 |
| 显式来源冲突与人工复核 | 通过 |
| Recall/MRR/重复/ACL/降级评测指标 | 通过 |
| 本地 CLI dry-run 和正式摄取 | 通过 |
| Ruff | 通过 |

## 真实源目录统计

`shared/laws/*.json` 和 `shared/rules/*.json` 共发现 7 个源文件、79 条记录、79 个 Chunk，0 个错误。dry-run 没有建立数据库连接，也没有写入项目数据。

## 发现并修复的问题

在临时 SQLite 上执行正式摄取时，首个文档插入失败，错误为 `NOT NULL constraint failed: knowledge_documents.created_at`。根因是 M1-A 迁移的时间戳列没有复现现有 `TimestampMixin` 的数据库默认值；模型测试使用 `create_all` 时没有暴露这个迁移差异。

已在 M1-A 迁移中为 `knowledge_documents` 和 `knowledge_chunks` 的 `created_at`、`updated_at` 增加 `CURRENT_TIMESTAMP` 默认值，并新增“迁移后正式摄取 + 重复摄取”回归用例。修复后该用例通过。

## 警告与限制

- 9 条 warning 来自既有依赖弃用提示和部分旧测试中的 `AsyncMock` 协程警告，没有导致失败。
- 5 个 skipped 是既有外部服务/可选依赖条件，不影响本地 SQLite M1-A 验证。
- 本阶段按约定没有启动 Docker，也没有连接阿里云、PostgreSQL、Redis 或远端向量服务；下周部署远端服务后再执行对应集成测试。
