# ContractOps 2.0 M0 测试报告

## 结论

通过。完整测试套件执行结果为 **368 passed, 5 skipped, 9 warnings**，总覆盖率 **74%**。

## 执行环境

- 日期：2026-09-09
- Python：3.12.5
- 平台：Windows
- 命令：`python -m pytest -q`
- 用例总数：373
- 执行耗时：123.80 秒
- 覆盖率目标：`server/`
- 覆盖率：5367 statements，1372 未覆盖，74%

## 跳过项

- 3 个外部服务集成用例因未配置环境变量跳过：`M0_BASE_URL`、`INTEGRATION_DATABASE_URL`、`INTEGRATION_REDIS_URL`。
- 2 个 Outlines 相关用例因当前环境没有安装可选依赖而跳过。
- PaddleOCR 真实运行时测试已执行并通过。

## 警告

本次有 9 条警告，主要是既有依赖弃用提示和测试中的 AsyncMock 协程警告；未导致测试失败。结果输出摘要见 [`pytest-output.txt`](./pytest-output.txt)。

## 覆盖率重点

M0 新增关键模块覆盖情况：

| 模块 | 覆盖率 |
|---|---:|
| `server/modules/contracts/models.py` | 100% |
| `server/modules/contracts/service.py` | 89% |
| `server/modules/jobs/models.py` | 100% |
| `server/modules/jobs/repository.py` | 76% |
| `server/modules/legacy_import/importer.py` | 68% |
| `server/modules/tenancy/auth.py` | 91% |
| `server/platform/observability.py` | 77% |
| `server/platform/rate_limit.py` | 71% |
| `server/workers/main.py` | 64% |

## 限制

当前机器没有 Docker，因此本次没有启动真实 PostgreSQL/Redis 容器，也没有执行基于容器的 M0 服务冒烟测试；这些入口已保留在 `tests/integration/` 和 CI 配置中。
