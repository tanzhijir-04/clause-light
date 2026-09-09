# ContractOps 2.0 M0 合同智能底座 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在保留 ClauseLight v1 可用性的同时，交付基于 PostgreSQL 的多租户合同版本、持久任务、Outbox、Redis 加速、可观测、OCR 稳定性和 v1 数据导入底座。

**Architecture:** 新能力进入 `/api/v2`，采用模块化单体和独立 Worker 进程。PostgreSQL 是合同、任务、审计和事件的唯一事实源；Redis 只保存可重建的限流、缓存和进度状态；v1 SQLite 通过只读幂等导入器迁移，不做原地修改。

**Tech Stack:** Python 3.10+、FastAPI、SQLAlchemy 2.0 async、PostgreSQL 16、Alembic、Redis 7、Pydantic Settings、OpenTelemetry、Prometheus、Docker Compose、pytest。

---

## 0. 实施约束与文件结构

执行分支必须是 `dev/2.0`。开始每个 Task 前运行：

```powershell
git branch --show-current
git status --short
```

预期分支为 `dev/2.0`。仓库中已有的 `docs/assets/` 和 2026-08-25 至 2026-08-30 论文计划属于用户内容，不加入本计划提交。

M0 完成后的文件职责如下：

```text
server/
├── api/v2.py                         # v2 路由聚合
├── modules/
│   ├── tenancy/
│   │   ├── models.py                 # Organization/User/Membership/ApiCredential
│   │   ├── auth.py                   # API Key 摘要验证和 TenantContext
│   │   └── api.py                    # 当前租户/凭据接口
│   ├── contracts/
│   │   ├── models.py                 # Contract/Version/Party/Clause/DocumentAsset
│   │   ├── schemas.py                # v2 请求响应 schema
│   │   ├── repository.py             # 带 organization_id 的持久化查询
│   │   ├── service.py                # 合同与版本应用服务
│   │   └── api.py                    # /api/v2/contracts
│   ├── jobs/
│   │   ├── models.py                 # ProcessingJob/JobStep
│   │   ├── repository.py             # 租约领取、检查点、完成/失败
│   │   ├── service.py                # 创建、取消和查询任务
│   │   └── api.py                    # /api/v2/jobs
│   ├── events/
│   │   ├── envelope.py               # 版本化领域事件信封
│   │   ├── models.py                 # OutboxEvent
│   │   └── outbox.py                 # 事务内追加事件
│   ├── audit/
│   │   ├── models.py                 # AuditEvent
│   │   └── service.py                # 脱敏审计写入
│   └── legacy_import/
│       ├── models.py                 # ImportBatch/LegacyIdMap
│       └── importer.py               # SQLite -> PostgreSQL 映射
├── models/base.py                    # SQLAlchemy Base 与通用 mixin
├── platform/
│   ├── database.py                   # engine/session/health
│   ├── redis.py                      # Redis 生命周期与降级
│   ├── rate_limit.py                 # 固定窗口限流
│   ├── progress.py                   # Redis 进度广播
│   └── observability.py              # request id、OTel、Prometheus
└── workers/main.py                   # PostgreSQL 任务 Worker 入口

migrations/                           # Alembic 环境和版本
scripts/import_v1_sqlite.py           # 导入 CLI
tests/v2/                             # M0 单元/集成/隔离/迁移测试
tests/integration/                    # PostgreSQL/Redis/OCR 真实依赖测试
.github/workflows/ci.yml              # CI
```

## Task 1：锁定运行配置和依赖边界

**Files:**
- Modify: `requirements.txt`
- Modify: `.env.example`
- Modify: `server/config.py`
- Create: `tests/v2/test_settings.py`

- [ ] **Step 1: 写生产配置失败测试**

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from server.config import Settings


def test_production_requires_postgres_and_redis() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            ENVIRONMENT="production",
            DATABASE_URL="sqlite+aiosqlite:///:memory:",
            REDIS_REQUIRED=True,
            REDIS_URL="",
        )


def test_test_environment_allows_sqlite_and_no_redis() -> None:
    settings = Settings(
        _env_file=None,
        ENVIRONMENT="test",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        REDIS_REQUIRED=False,
        REDIS_URL="",
    )
    assert settings.ENVIRONMENT == "test"
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `pytest tests/v2/test_settings.py -q`
Expected: FAIL，因为 `Settings` 尚无 `ENVIRONMENT`、`REDIS_URL` 和生产校验。

- [ ] **Step 3: 在 `server/config.py` 增加明确配置**

在 `Settings` 中加入：

```python
from typing import Literal

from pydantic import model_validator


Environment = Literal["development", "test", "production"]


class Settings(BaseSettings):
    ENVIRONMENT: Environment = "development"
    DATABASE_URL: str = "postgresql+asyncpg://clauselight:clauselight@localhost:5432/clauselight"
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_REQUIRED: bool = False
    AUTH_PEPPER: str = "development-only-change-me"
    JOB_LEASE_SECONDS: int = 60
    JOB_POLL_INTERVAL_SECONDS: float = 1.0
    OTEL_ENABLED: bool = False
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ""
    METRICS_ENABLED: bool = True

    @model_validator(mode="after")
    def validate_runtime_dependencies(self) -> "Settings":
        if self.ENVIRONMENT == "production":
            if not self.DATABASE_URL.startswith("postgresql+"):
                raise ValueError("production DATABASE_URL 必须使用 PostgreSQL async driver")
            if self.REDIS_REQUIRED and not self.REDIS_URL:
                raise ValueError("production REDIS_REQUIRED=true 时必须配置 REDIS_URL")
            if self.AUTH_PEPPER == "development-only-change-me":
                raise ValueError("production 必须设置 AUTH_PEPPER")
        return self
```

保留 v1 已有字段；只删除旧的 SQLite `DATABASE_URL` 默认值，避免重复定义。

- [ ] **Step 4: 更新依赖**

将 `requirements.txt` 中 Paddle 两行替换并加入：

```text
asyncpg>=0.29,<1.0
alembic>=1.13,<2.0
redis>=5.0,<6.0
opentelemetry-api>=1.27,<2.0
opentelemetry-sdk>=1.27,<2.0
opentelemetry-instrumentation-fastapi>=0.48b0,<1.0
opentelemetry-exporter-otlp-proto-http>=1.27,<2.0
prometheus-client>=0.21,<1.0
paddlepaddle==2.6.2
paddleocr==2.9.1
```

在 `.env.example` 加入与 `Settings` 同名的生产配置示例，示例凭据只能使用 `change-me`，不得出现真实密钥。

- [ ] **Step 5: 验证配置测试和依赖冲突**

Run: `pytest tests/v2/test_settings.py -q`
Expected: `2 passed`。

Run: `python -m pip check`
Expected: `No broken requirements found.`

- [ ] **Step 6: 提交**

```powershell
git add requirements.txt .env.example server/config.py tests/v2/test_settings.py
git commit -m ":wrench: ai-feat(修改) 锁定2.0运行配置与依赖"
```

## Task 2：建立共享 Base、PostgreSQL Session 和 Alembic

**Files:**
- Create: `server/models/base.py`
- Create: `server/platform/__init__.py`
- Create: `server/platform/database.py`
- Modify: `server/models/database.py`
- Create: `alembic.ini`
- Create: `migrations/env.py`
- Create: `migrations/script.py.mako`
- Create: `tests/v2/conftest.py`
- Create: `tests/v2/test_database_platform.py`

- [ ] **Step 1: 写 Session 事务测试**

```python
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from server.platform.database import session_scope


@pytest.mark.asyncio
async def test_session_scope_commits_and_rolls_back() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.execute(text("CREATE TABLE sample (value INTEGER NOT NULL)"))

    async with session_scope(factory) as session:
        await session.execute(text("INSERT INTO sample(value) VALUES (1)"))

    with pytest.raises(RuntimeError):
        async with session_scope(factory) as session:
            await session.execute(text("INSERT INTO sample(value) VALUES (2)"))
            raise RuntimeError("rollback")

    async with factory() as session:
        count = (await session.execute(text("SELECT COUNT(*) FROM sample"))).scalar_one()
    assert count == 1
    await engine.dispose()
```

- [ ] **Step 2: 运行测试并确认导入失败**

Run: `pytest tests/v2/test_database_platform.py -q`
Expected: FAIL，因为 `server.platform.database` 尚不存在。

- [ ] **Step 3: 创建 Base 和数据库生命周期**

`server/models/base.py`：

```python
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

`server/platform/database.py`：

```python
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from server.config import settings


engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG, pool_pre_ping=True)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def session_scope(
    factory: async_sessionmaker[AsyncSession] = async_session_factory,
) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db() -> AsyncIterator[AsyncSession]:
    async with session_scope() as session:
        yield session


async def database_is_ready(target_engine: AsyncEngine = engine) -> bool:
    try:
        async with target_engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
```

`tests/v2/conftest.py` 提供后续 Task 共用的隔离 Session：

```python
from __future__ import annotations

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from server.models.base import Base


@pytest_asyncio.fixture
async def v2_session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()
```

在 `server/models/database.py` 中改为从 `server.models.base` 导入 `Base`，并从 `server.platform.database` 重新导出 `engine`、`async_session_factory` 和 `get_db`。M0 不再在应用启动时执行 `create_all` 或拼接 `ALTER TABLE`；schema 只能由 Alembic 管理。

- [ ] **Step 4: 创建 Alembic 环境**

`migrations/env.py` 必须导入所有模型以注册 metadata，并读取同一个 `DATABASE_URL`：

```python
from __future__ import annotations

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from server.config import settings
from server.models.base import Base
import server.models.database


config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio

    asyncio.run(run_async_migrations())
```

`alembic.ini` 使用 `script_location = migrations`，并把日志等级设为 `WARN`，禁止输出连接串中的密码。

- [ ] **Step 5: 验证**

Run: `pytest tests/v2/test_database_platform.py -q`
Expected: `1 passed`。

Run: `alembic heads`
Expected: 命令成功；在首个 revision 创建前不输出 revision ID。

- [ ] **Step 6: 提交**

```powershell
git add server/models/base.py server/platform server/models/database.py alembic.ini migrations tests/v2/conftest.py tests/v2/test_database_platform.py
git commit -m ":sparkles: ai-feat(新增) 建立PostgreSQL与Alembic底座"
```

## Task 3：建立租户、合同版本、任务、Outbox 和审计模型

**Files:**
- Create: `server/modules/__init__.py`
- Create: `server/modules/tenancy/__init__.py`
- Create: `server/modules/tenancy/models.py`
- Create: `server/modules/contracts/__init__.py`
- Create: `server/modules/contracts/models.py`
- Create: `server/modules/jobs/__init__.py`
- Create: `server/modules/jobs/models.py`
- Create: `server/modules/events/__init__.py`
- Create: `server/modules/events/models.py`
- Create: `server/modules/audit/__init__.py`
- Create: `server/modules/audit/models.py`
- Create: `server/modules/legacy_import/__init__.py`
- Create: `server/modules/legacy_import/models.py`
- Modify: `migrations/env.py`
- Create: `migrations/versions/20260909_0001_contractops_foundation.py`
- Create: `tests/v2/test_foundation_models.py`

- [ ] **Step 1: 写领域不变量测试**

```python
from __future__ import annotations

from server.modules.contracts.models import ContractVersion
from server.modules.events.models import OutboxEvent
from server.modules.jobs.models import ProcessingJob


def test_foundation_tables_and_idempotency_constraints() -> None:
    version_constraints = {item.name for item in ContractVersion.__table__.constraints}
    job_constraints = {item.name for item in ProcessingJob.__table__.constraints}
    outbox_constraints = {item.name for item in OutboxEvent.__table__.constraints}

    assert "uq_contract_versions_contract_number" in version_constraints
    assert "uq_processing_jobs_org_idempotency" in job_constraints
    assert "uq_outbox_events_event_id" in outbox_constraints
```

- [ ] **Step 2: 运行测试并确认模型缺失**

Run: `pytest tests/v2/test_foundation_models.py -q`
Expected: FAIL，因为模块尚不存在。

- [ ] **Step 3: 实现租户模型**

`server/modules/tenancy/models.py` 定义：

```python
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from server.models.base import Base, TimestampMixin


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))


class Membership(TimestampMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("organization_id", "user_id"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(32), default="member")


class ApiCredential(TimestampMixin, Base):
    __tablename__ = "api_credentials"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    key_prefix: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    key_digest: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="active")
```

- [ ] **Step 4: 实现合同和文件模型**

`server/modules/contracts/models.py` 使用不可变版本号约束：

```python
from __future__ import annotations

import uuid

from sqlalchemy import BigInteger, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from server.models.base import Base, TimestampMixin


class Contract(TimestampMixin, Base):
    __tablename__ = "contract_records"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    contract_type: Mapped[str] = mapped_column(String(80), default="other")
    lifecycle_status: Mapped[str] = mapped_column(String(32), default="draft")


class ContractVersion(TimestampMixin, Base):
    __tablename__ = "contract_versions"
    __table_args__ = (
        UniqueConstraint("contract_id", "version_number", name="uq_contract_versions_contract_number"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    contract_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contract_records.id"), index=True)
    version_number: Mapped[int]
    text_content: Mapped[str | None] = mapped_column(Text)
    content_sha256: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(32), default="upload")


class ContractParty(TimestampMixin, Base):
    __tablename__ = "contract_parties"
    __table_args__ = (
        UniqueConstraint(
            "contract_version_id",
            "role",
            "normalized_name",
            name="uq_contract_parties_version_role_name",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    contract_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contract_versions.id"), index=True)
    role: Mapped[str] = mapped_column(String(40))
    display_name: Mapped[str] = mapped_column(String(300))
    normalized_name: Mapped[str] = mapped_column(String(300), index=True)


class Clause(TimestampMixin, Base):
    __tablename__ = "contract_clauses"
    __table_args__ = (
        UniqueConstraint("contract_version_id", "ordinal", name="uq_contract_clauses_version_ordinal"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    contract_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contract_versions.id"), index=True)
    ordinal: Mapped[int]
    heading: Mapped[str | None] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text)
    source_start: Mapped[int]
    source_end: Mapped[int]
    content_sha256: Mapped[str] = mapped_column(String(64), index=True)


class DocumentAsset(TimestampMixin, Base):
    __tablename__ = "document_assets"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    contract_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contract_versions.id"), index=True)
    filename: Mapped[str] = mapped_column(String(300))
    media_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    content_sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
    parse_status: Mapped[str] = mapped_column(String(32), default="pending")
```

- [ ] **Step 5: 实现任务、Outbox、审计和导入模型**

模型必须包含下列唯一约束和状态字段：

```python
class ProcessingJob(TimestampMixin, Base):
    __tablename__ = "processing_jobs"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_processing_jobs_org_idempotency"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    job_type: Mapped[str] = mapped_column(String(80), index=True)
    aggregate_type: Mapped[str] = mapped_column(String(80))
    aggregate_id: Mapped[uuid.UUID]
    idempotency_key: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    current_step: Mapped[str | None] = mapped_column(String(80))
    attempts: Mapped[int] = mapped_column(default=0)
    lease_owner: Mapped[str | None] = mapped_column(String(120))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(80))


class JobStep(TimestampMixin, Base):
    __tablename__ = "job_steps"
    __table_args__ = (UniqueConstraint("job_id", "step_key", name="uq_job_steps_job_key"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("processing_jobs.id"), index=True)
    step_key: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(24), default="pending")
    output_json: Mapped[dict | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(80))


class OutboxEvent(TimestampMixin, Base):
    __tablename__ = "outbox_events"
    __table_args__ = (UniqueConstraint("event_id", name="uq_outbox_events_event_id"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(index=True)
    event_type: Mapped[str] = mapped_column(String(160), index=True)
    schema_version: Mapped[int] = mapped_column(default=1)
    aggregate_type: Mapped[str] = mapped_column(String(80))
    aggregate_id: Mapped[uuid.UUID]
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(index=True)
    actor_type: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[str] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(160), index=True)
    resource_type: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str] = mapped_column(String(120), index=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    detail: Mapped[dict] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ImportBatch(TimestampMixin, Base):
    __tablename__ = "import_batches"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_sha256: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(24), default="running")
    counts: Mapped[dict] = mapped_column(JSON, default=dict)


class LegacyIdMap(Base):
    __tablename__ = "legacy_id_maps"
    __table_args__ = (
        UniqueConstraint("batch_id", "entity_type", "legacy_id", name="uq_legacy_id_maps_source"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("import_batches.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(80))
    legacy_id: Mapped[str] = mapped_column(String(120))
    new_id: Mapped[uuid.UUID]
```

把每个类放入文件结构指定的模块，并补齐 `uuid`、`datetime`、`DateTime`、`JSON`、`ForeignKey`、`String`、`UniqueConstraint`、`func`、`Mapped`、`mapped_column` 导入。

- [ ] **Step 6: 创建 Alembic 首版迁移并验证可逆**

先在 `migrations/env.py` 增加显式模型导入，保证 autogenerate 能看到新表：

```python
import server.modules.audit.models
import server.modules.contracts.models
import server.modules.events.models
import server.modules.jobs.models
import server.modules.legacy_import.models
import server.modules.tenancy.models
```

Run: `alembic revision --autogenerate -m "contractops foundation" --rev-id 20260909_0001`
Expected: 生成 `migrations/versions/20260909_0001_contractops_foundation.py`，包含本 Task 的新表和现有 v1 表。

检查迁移文件：`upgrade()` 必须先建租户表，再建带外键的合同表；`downgrade()` 以逆序删除。不得手工删除 v1 表数据。

Run: `alembic upgrade head`
Expected: 空 PostgreSQL 创建全部表。

Run: `alembic downgrade base`
Expected: 迁移完整回退且无外键顺序错误。

Run: `alembic upgrade head`
Expected: 第二次升级成功。

- [ ] **Step 7: 运行模型测试并提交**

Run: `pytest tests/v2/test_foundation_models.py -q`
Expected: `1 passed`。

```powershell
git add server/modules server/models/base.py migrations tests/v2/test_foundation_models.py
git commit -m ":card_file_box: ai-feat(新增) 建立合同智能底座领域模型"
```

## Task 4：实现事件信封、事务 Outbox 和合同版本服务

**Files:**
- Create: `server/modules/events/envelope.py`
- Create: `server/modules/events/outbox.py`
- Create: `server/modules/contracts/schemas.py`
- Create: `server/modules/contracts/repository.py`
- Create: `server/modules/contracts/service.py`
- Create: `tests/v2/test_contract_service.py`

- [ ] **Step 1: 写幂等合同创建测试**

```python
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from server.modules.contracts.models import Contract, ContractVersion
from server.modules.contracts.service import ContractService
from server.modules.events.models import OutboxEvent


@pytest.mark.asyncio
async def test_create_contract_is_idempotent(v2_session) -> None:
    organization_id = uuid.uuid4()
    service = ContractService(v2_session)
    first = await service.create_contract(
        organization_id=organization_id,
        title="采购框架合同",
        contract_type="procurement",
        text_content="第一条 合同标的",
        idempotency_key="upload-001",
    )
    second = await service.create_contract(
        organization_id=organization_id,
        title="采购框架合同",
        contract_type="procurement",
        text_content="第一条 合同标的",
        idempotency_key="upload-001",
    )
    assert first.contract_id == second.contract_id
    assert (await v2_session.scalar(select(func.count()).select_from(Contract))) == 1
    assert (await v2_session.scalar(select(func.count()).select_from(ContractVersion))) == 1
    assert (await v2_session.scalar(select(func.count()).select_from(OutboxEvent))) == 1
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `pytest tests/v2/test_contract_service.py -q`
Expected: FAIL，因为服务尚不存在。

- [ ] **Step 3: 定义版本化事件信封**

`server/modules/events/envelope.py`：

```python
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class EventEnvelope(BaseModel):
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    event_type: str
    schema_version: int = 1
    organization_id: uuid.UUID
    aggregate_type: str
    aggregate_id: uuid.UUID
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: dict
```

`server/modules/events/outbox.py` 只负责把信封转换为 ORM 行并加入当前 Session，不自行提交事务：

```python
from sqlalchemy.ext.asyncio import AsyncSession

from server.modules.events.envelope import EventEnvelope
from server.modules.events.models import OutboxEvent


def append_outbox(session: AsyncSession, envelope: EventEnvelope) -> OutboxEvent:
    row = OutboxEvent(
        event_id=envelope.event_id,
        event_type=envelope.event_type,
        schema_version=envelope.schema_version,
        organization_id=envelope.organization_id,
        aggregate_type=envelope.aggregate_type,
        aggregate_id=envelope.aggregate_id,
        payload=envelope.model_dump(mode="json"),
    )
    session.add(row)
    return row
```

- [ ] **Step 4: 实现合同应用服务**

`ContractService.create_contract()` 必须：

1. 先按 `(organization_id, idempotency_key)` 查询 `ProcessingJob`；
2. 已存在时返回原合同和版本；
3. 计算规范化文本 SHA-256；
4. 创建 `Contract` 和 `ContractVersion(version_number=1)`；
5. 创建 `ProcessingJob(job_type="document.ingest")`；
6. 追加 `contract.version.created` Outbox；
7. 只调用 `flush()`，提交由请求级 Session 完成。

核心实现：

```python
normalized = text_content.replace("\r\n", "\n").strip()
digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
contract = Contract(
    organization_id=organization_id,
    title=title,
    contract_type=contract_type,
)
self.session.add(contract)
await self.session.flush()
version = ContractVersion(
    organization_id=organization_id,
    contract_id=contract.id,
    version_number=1,
    text_content=normalized,
    content_sha256=digest,
)
self.session.add(version)
job = ProcessingJob(
    organization_id=organization_id,
    job_type="document.ingest",
    aggregate_type="contract_version",
    aggregate_id=version.id,
    idempotency_key=idempotency_key,
)
self.session.add(job)
append_outbox(
    self.session,
    EventEnvelope(
        event_type="contract.version.created",
        organization_id=organization_id,
        aggregate_type="contract_version",
        aggregate_id=version.id,
        payload={"contract_id": str(contract.id), "version_number": 1, "job_id": str(job.id)},
    ),
)
await self.session.flush()
```

并捕获唯一约束竞争产生的 `IntegrityError`：回滚到 Savepoint 后重新查询幂等记录，不得用裸 `except`。

- [ ] **Step 5: 验证并提交**

Run: `pytest tests/v2/test_contract_service.py -q`
Expected: `1 passed`。

```powershell
git add server/modules/events server/modules/contracts tests/v2/test_contract_service.py
git commit -m ":sparkles: ai-feat(新功能) 实现幂等合同版本与事务事件"
```

## Task 5：实现 PostgreSQL 持久任务、检查点和恢复 Worker

**Files:**
- Create: `server/modules/jobs/repository.py`
- Create: `server/modules/jobs/service.py`
- Create: `server/workers/__init__.py`
- Create: `server/workers/main.py`
- Create: `server/workers/errors.py`
- Create: `tests/v2/test_job_repository.py`
- Create: `tests/v2/test_job_recovery.py`

- [ ] **Step 1: 写领取互斥和恢复测试**

```python
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from server.modules.jobs.repository import JobRepository


@pytest.mark.asyncio
async def test_expired_lease_can_be_reclaimed(v2_session, queued_job) -> None:
    queued_job.status = "running"
    queued_job.lease_owner = "dead-worker"
    queued_job.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await v2_session.flush()

    claimed = await JobRepository(v2_session).claim_next(
        worker_id="replacement-worker",
        lease_seconds=60,
    )
    assert claimed is not None
    assert claimed.id == queued_job.id
    assert claimed.lease_owner == "replacement-worker"
    assert claimed.attempts == 1
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `pytest tests/v2/test_job_repository.py tests/v2/test_job_recovery.py -q`
Expected: FAIL，因为 `JobRepository` 尚不存在。

- [ ] **Step 3: 实现原子领取**

`claim_next()` 使用 PostgreSQL 行锁；SQLite 单元测试只验证状态转换，PostgreSQL 集成测试验证两个并发 Session 不能领取同一任务：

```python
now = datetime.now(UTC)
query = (
    select(ProcessingJob)
    .where(
        or_(
            ProcessingJob.status == "queued",
            and_(
                ProcessingJob.status == "running",
                ProcessingJob.lease_expires_at < now,
            ),
        )
    )
    .order_by(ProcessingJob.created_at)
    .with_for_update(skip_locked=True)
    .limit(1)
)
job = (await self.session.execute(query)).scalar_one_or_none()
if job is None:
    return None
job.status = "running"
job.lease_owner = worker_id
job.lease_expires_at = now + timedelta(seconds=lease_seconds)
job.attempts += 1
await self.session.flush()
return job
```

- [ ] **Step 4: 实现检查点和 Worker 循环**

`JobRepository.complete_step()` 以 `(job_id, step_key)` Upsert，重复执行返回原输出。`server/workers/main.py` 使用显式处理器注册表：

```python
class RetryableJobError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


JobHandler = Callable[[ProcessingJob, AsyncSession], Awaitable[None]]
HANDLERS: dict[str, JobHandler] = {}


def register_handler(job_type: str, handler: JobHandler) -> None:
    if job_type in HANDLERS:
        raise ValueError(f"重复注册任务处理器: {job_type}")
    HANDLERS[job_type] = handler


async def run_once(worker_id: str) -> bool:
    async with session_scope() as session:
        repository = JobRepository(session)
        job = await repository.claim_next(worker_id, settings.JOB_LEASE_SECONDS)
        if job is None:
            return False
        handler = HANDLERS.get(job.job_type)
        if handler is None:
            await repository.fail(job, "HANDLER_NOT_FOUND")
            return True
        try:
            await handler(job, session)
            await repository.complete(job)
        except RetryableJobError as error:
            await repository.retry(job, error.code)
        except Exception as error:
            logger.exception("任务失败: job_id=%s error_type=%s", job.id, type(error).__name__)
            await repository.fail(job, type(error).__name__)
        return True
```

日志只记录任务 ID 和错误类型，不记录合同正文。

- [ ] **Step 5: 验证 PostgreSQL 并发行为**

Run: `pytest tests/v2/test_job_repository.py tests/v2/test_job_recovery.py -q`
Expected: 单元测试全部通过。

Run: `pytest tests/integration/test_postgres_job_claim.py -q -m integration`
Expected: 两个并发 Worker 只领取一个任务。

- [ ] **Step 6: 提交**

```powershell
git add server/modules/jobs server/workers tests/v2/test_job_repository.py tests/v2/test_job_recovery.py tests/integration/test_postgres_job_claim.py
git commit -m ":construction_worker: ai-feat(新增) 增加可恢复的持久任务Worker"
```

## Task 6：接入 Redis 限流和任务进度广播

**Files:**
- Create: `server/platform/redis.py`
- Create: `server/platform/rate_limit.py`
- Create: `server/platform/progress.py`
- Create: `tests/v2/test_rate_limit.py`
- Create: `tests/v2/test_progress_fallback.py`
- Create: `tests/integration/test_redis_platform.py`

- [ ] **Step 1: 写 Redis 不可用时的降级测试**

```python
from __future__ import annotations

import pytest

from server.platform.progress import ProgressPublisher


@pytest.mark.asyncio
async def test_progress_falls_back_without_losing_final_state() -> None:
    publisher = ProgressPublisher(redis_client=None)
    await publisher.publish("job-1", {"status": "running", "percent": 40})
    assert publisher.local_snapshot("job-1") == {"status": "running", "percent": 40}
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `pytest tests/v2/test_rate_limit.py tests/v2/test_progress_fallback.py -q`
Expected: FAIL，因为 Redis 平台模块尚不存在。

- [ ] **Step 3: 实现 Redis 生命周期**

`server/platform/redis.py`：

```python
from __future__ import annotations

import logging

from redis.asyncio import Redis

from server.config import settings

logger = logging.getLogger(__name__)


async def create_redis_client() -> Redis | None:
    if not settings.REDIS_URL:
        return None
    client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        await client.ping()
        return client
    except Exception as error:
        await client.aclose()
        if settings.REDIS_REQUIRED:
            raise RuntimeError("Redis 为生产必需依赖但当前不可用") from error
        logger.warning("Redis 不可用，启用进程内降级: %s", type(error).__name__)
        return None
```

- [ ] **Step 4: 实现固定窗口限流**

`RateLimiter.allow(key, limit, window_seconds)` 使用 Redis `INCR`，第一次计数设置 `EXPIRE`；无 Redis 时使用带单调时钟和 `asyncio.Lock` 的进程内字典。返回值固定为：

```python
@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after_seconds: int
```

生产配置 `REDIS_REQUIRED=true` 时不会进入进程内降级，因此多实例限流不会产生不一致承诺。

- [ ] **Step 5: 实现进度广播**

`ProgressPublisher.publish()` 先更新本地快照，再向 `clauselight:jobs:{job_id}` 发布 JSON。最终状态仍由 PostgreSQL `ProcessingJob.status` 提供，API 订阅断线后必须从数据库补齐。

- [ ] **Step 6: 验证**

Run: `pytest tests/v2/test_rate_limit.py tests/v2/test_progress_fallback.py -q`
Expected: 限流边界和无 Redis 降级全部通过。

Run: `pytest tests/integration/test_redis_platform.py -q -m integration`
Expected: 计数过期、进度发布和重新连接通过。

- [ ] **Step 7: 提交**

```powershell
git add server/platform/redis.py server/platform/rate_limit.py server/platform/progress.py tests/v2/test_rate_limit.py tests/v2/test_progress_fallback.py tests/integration/test_redis_platform.py
git commit -m ":zap: ai-feat(新增) 接入Redis限流与进度广播"
```

## Task 7：实现租户 API Key、审计脱敏和跨租户隔离

**Files:**
- Create: `server/modules/tenancy/auth.py`
- Create: `server/modules/tenancy/api.py`
- Create: `server/modules/audit/service.py`
- Create: `tests/v2/test_tenant_auth.py`
- Create: `tests/v2/test_tenant_isolation.py`
- Create: `tests/v2/test_audit_redaction.py`

- [ ] **Step 1: 写认证和隔离测试**

```python
from __future__ import annotations

import uuid

from server.modules.tenancy.auth import digest_api_key


def test_api_key_digest_never_contains_secret() -> None:
    secret = "cl_live_sensitive-value"
    digest = digest_api_key(secret, "pepper")
    assert secret not in digest
    assert len(digest) == 64


async def test_org_a_cannot_read_org_b_contract(v2_client, org_a_key, org_b_contract) -> None:
    response = await v2_client.get(
        f"/api/v2/contracts/{org_b_contract.id}",
        headers={"X-API-Key": org_a_key},
    )
    assert response.status_code == 404
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `pytest tests/v2/test_tenant_auth.py tests/v2/test_tenant_isolation.py tests/v2/test_audit_redaction.py -q`
Expected: FAIL，因为 v2 租户认证尚不存在。

- [ ] **Step 3: 实现安全摘要和上下文**

```python
from __future__ import annotations

import hashlib
import hmac
import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class TenantContext:
    organization_id: uuid.UUID
    credential_id: uuid.UUID
    actor_id: str


def digest_api_key(api_key: str, pepper: str) -> str:
    return hmac.new(pepper.encode("utf-8"), api_key.encode("utf-8"), hashlib.sha256).hexdigest()
```

`require_tenant()` 只按 API Key 前缀查候选凭据，再用 `hmac.compare_digest()` 比较摘要；错误响应统一返回 401，不泄露前缀是否存在。认证成功后以 `TenantContext` 注入所有 `/api/v2` 仓储。

- [ ] **Step 4: 实现审计脱敏**

`AuditService.record()` 拒绝以下 detail 键：`contract_text`、`ocr_text`、`prompt`、`response`、`api_key`、`authorization`。允许的模型调用审计字段限定为 `provider`、`model`、`input_tokens`、`output_tokens`、`latency_ms`、`success`、`error_type`。

```python
SENSITIVE_KEYS = {
    "contract_text",
    "ocr_text",
    "prompt",
    "response",
    "api_key",
    "authorization",
}


def redact_detail(detail: dict) -> dict:
    return {
        key: "[REDACTED]" if key.lower() in SENSITIVE_KEYS else value
        for key, value in detail.items()
    }
```

- [ ] **Step 5: 验证并提交**

Run: `pytest tests/v2/test_tenant_auth.py tests/v2/test_tenant_isolation.py tests/v2/test_audit_redaction.py -q`
Expected: 摘要、401、404 隔离和脱敏测试全部通过。

```powershell
git add server/modules/tenancy server/modules/audit tests/v2/test_tenant_auth.py tests/v2/test_tenant_isolation.py tests/v2/test_audit_redaction.py
git commit -m ":lock: ai-feat(新增) 增加租户认证隔离与脱敏审计"
```

## Task 8：交付 `/api/v2` 合同与任务 API

**Files:**
- Create: `server/modules/contracts/api.py`
- Create: `server/modules/jobs/api.py`
- Create: `server/api/v2.py`
- Modify: `server/main.py`
- Create: `tests/v2/test_contract_api.py`
- Create: `tests/v2/test_job_api.py`

- [ ] **Step 1: 写 API 契约测试**

```python
from __future__ import annotations


async def test_create_contract_returns_version_and_job(v2_client, org_api_key) -> None:
    response = await v2_client.post(
        "/api/v2/contracts",
        headers={"X-API-Key": org_api_key, "Idempotency-Key": "contract-001"},
        json={
            "title": "采购框架合同",
            "contract_type": "procurement",
            "text_content": "第一条 合同标的",
        },
    )
    assert response.status_code == 202
    body = response.json()
    assert set(body) == {"contract_id", "version_id", "job_id", "status"}
    assert body["status"] == "queued"


async def test_create_contract_requires_idempotency_key(v2_client, org_api_key) -> None:
    response = await v2_client.post(
        "/api/v2/contracts",
        headers={"X-API-Key": org_api_key},
        json={"title": "合同", "contract_type": "other", "text_content": "正文"},
    )
    assert response.status_code == 400
```

- [ ] **Step 2: 运行测试并确认 404**

Run: `pytest tests/v2/test_contract_api.py tests/v2/test_job_api.py -q`
Expected: FAIL，`/api/v2` 尚未注册。

- [ ] **Step 3: 实现 schema 和路由**

`server/modules/contracts/schemas.py`：

```python
from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class ContractCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    contract_type: str = Field(min_length=1, max_length=80)
    text_content: str = Field(min_length=1, max_length=2_000_000)


class ContractAcceptedResponse(BaseModel):
    contract_id: uuid.UUID
    version_id: uuid.UUID
    job_id: uuid.UUID
    status: str = "queued"
```

提供下列端点：

```text
POST /api/v2/contracts
GET  /api/v2/contracts/{contract_id}
GET  /api/v2/contracts/{contract_id}/versions
GET  /api/v2/jobs/{job_id}
POST /api/v2/jobs/{job_id}/cancel
GET  /api/v2/jobs/{job_id}/events
```

所有资源查询同时过滤 `id` 和 `organization_id`。不存在和跨租户统一返回 404。创建接口要求 `Idempotency-Key`，成功返回 202。

- [ ] **Step 4: 注册 v2 聚合路由**

`server/api/v2.py`：

```python
from fastapi import APIRouter

from server.modules.contracts.api import router as contracts_router
from server.modules.jobs.api import router as jobs_router
from server.modules.tenancy.api import router as tenancy_router


router = APIRouter(prefix="/api/v2")
router.include_router(tenancy_router, prefix="/tenancy", tags=["v2-tenancy"])
router.include_router(contracts_router, prefix="/contracts", tags=["v2-contracts"])
router.include_router(jobs_router, prefix="/jobs", tags=["v2-jobs"])
```

在 `server/main.py` 创建 FastAPI 后调用 `app.include_router(v2_router)`；保留 v1 路由。

- [ ] **Step 5: 验证并提交**

Run: `pytest tests/v2/test_contract_api.py tests/v2/test_job_api.py -q`
Expected: API 契约测试全部通过。

Run: `pytest tests/test_api_contracts.py tests/test_main.py -q`
Expected: v1 合同和主入口回归测试通过。

```powershell
git add server/modules/contracts/api.py server/modules/contracts/schemas.py server/modules/jobs/api.py server/api/v2.py server/main.py tests/v2/test_contract_api.py tests/v2/test_job_api.py
git commit -m ":sparkles: ai-feat(新功能) 交付合同与任务v2接口"
```

## Task 9：实现 v1 SQLite 只读幂等导入器

**Files:**
- Create: `server/modules/legacy_import/importer.py`
- Create: `scripts/import_v1_sqlite.py`
- Create: `tests/v2/test_legacy_importer.py`
- Create: `tests/v2/test_legacy_import_idempotency.py`

- [ ] **Step 1: 写 dry-run 和重复导入测试**

```python
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from server.modules.contracts.models import Contract
from server.modules.legacy_import.importer import LegacyImporter


@pytest.mark.asyncio
async def test_dry_run_does_not_write(v1_sqlite_path, v2_session) -> None:
    report = await LegacyImporter(v2_session).run(v1_sqlite_path, dry_run=True)
    assert report.source_counts["contracts"] == 1
    assert (await v2_session.scalar(select(func.count()).select_from(Contract))) == 0


@pytest.mark.asyncio
async def test_repeated_import_does_not_duplicate(v1_sqlite_path, v2_session) -> None:
    importer = LegacyImporter(v2_session)
    first = await importer.run(v1_sqlite_path, dry_run=False)
    second = await importer.run(v1_sqlite_path, dry_run=False)
    assert first.batch_id == second.batch_id
    assert (await v2_session.scalar(select(func.count()).select_from(Contract))) == 1
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `pytest tests/v2/test_legacy_importer.py tests/v2/test_legacy_import_idempotency.py -q`
Expected: FAIL，因为导入器尚不存在。

- [ ] **Step 3: 实现只读打开和源摘要**

```python
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path


def source_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def open_readonly(path: Path) -> sqlite3.Connection:
    resolved = path.resolve(strict=True)
    connection = sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection
```

- [ ] **Step 4: 实现映射顺序和校验报告**

导入顺序固定为：

```text
organizations/default -> contracts -> analyses -> clause_analyses
knowledge_rules -> legal_references
memory_sessions -> memory_events -> memory_atoms -> memory_scenarios -> memory_personas
skills -> wiki_pages -> wiki_links -> asset_audit_log
```

每个旧 ID 都写入 `LegacyIdMap`。无法映射的行写入报告的 `rejected_rows`，包括 `entity_type`、`legacy_id` 和稳定错误码，不包含正文。只有所有源计数、写入计数和拒绝计数相加一致时，`ImportBatch.status` 才能变为 `completed`。

CLI：

```python
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--organization-name", default="ClauseLight v1 Import")
parser.add_argument("--dry-run", action="store_true")
parser.add_argument("--report", type=Path, default=Path("data/import-report.json"))
```

默认不删除、不重命名、不写入源 SQLite。

- [ ] **Step 5: 验证并提交**

Run: `pytest tests/v2/test_legacy_importer.py tests/v2/test_legacy_import_idempotency.py -q`
Expected: dry-run、完整导入、重复导入和坏外键报告测试全部通过。

Run: `python scripts/import_v1_sqlite.py --source data/clause_light.db --dry-run --report data/import-report.json`
Expected: 输出源摘要和逐表计数，源文件修改时间及 SHA-256 在命令前后不变。

```powershell
git add server/modules/legacy_import scripts/import_v1_sqlite.py tests/v2/test_legacy_importer.py tests/v2/test_legacy_import_idempotency.py
git commit -m ":truck: ai-feat(新增) 增加v1数据幂等导入器"
```

## Task 10：修复 PaddleOCR 版本漂移并建立真实冒烟门

**Files:**
- Modify: `server/core/ocr.py`
- Modify: `tests/test_ocr.py`
- Create: `tests/fixtures/ocr/simple_chinese_contract.png`
- Create: `tests/integration/test_ocr_runtime.py`
- Modify: `pytest.ini`

- [ ] **Step 1: 写构造参数与真实图片测试**

```python
from __future__ import annotations

import pytest

from server.core.ocr import OCREngine


@pytest.mark.asyncio
@pytest.mark.ocr_integration
async def test_paddleocr_runtime_reads_fixed_fixture() -> None:
    engine = OCREngine()
    result = await engine.recognize("tests/fixtures/ocr/simple_chinese_contract.png")
    assert result.text.strip()
    assert "合同" in result.text
```

- [ ] **Step 2: 在当前错误环境复现失败并记录错误码**

Run: `pytest tests/integration/test_ocr_runtime.py -q -m ocr_integration`
Expected before fix: FAIL，当前已观察到 PaddleOCR 3.x 对 `use_gpu` 报 `Unknown argument`；测试日志不得包含图片正文。

- [ ] **Step 3: 让 OCR 封装只面向已锁定 2.x API**

`server/core/ocr.py` 在实例化前验证主版本：

```python
from importlib.metadata import version


def ensure_supported_paddleocr_version() -> None:
    installed = version("paddleocr")
    major = int(installed.split(".", maxsplit=1)[0])
    if major != 2:
        raise RuntimeError(
            f"ClauseLight OCR requires paddleocr 2.x, installed={installed}. "
            "Run: python -m pip install -r requirements.txt"
        )
```

构造参数继续使用 v2 支持的 `use_gpu`、`det_model_dir`、`rec_model_dir`；模型不可用时返回已有的显式降级结果，不吞异常。

- [ ] **Step 4: 验证单元和真实运行时**

Run: `pytest tests/test_ocr.py -q`
Expected: mock 单元测试全部通过。

Run: `pytest tests/integration/test_ocr_runtime.py -q -m ocr_integration`
Expected: 固定图片识别出“合同”。

- [ ] **Step 5: 提交**

```powershell
git add requirements.txt server/core/ocr.py tests/test_ocr.py tests/fixtures/ocr/simple_chinese_contract.png tests/integration/test_ocr_runtime.py pytest.ini
git commit -m ":bug: ai-feat(修复) 固定OCR运行时并增加真实冒烟测试"
```

## Task 11：加入请求追踪、Prometheus 指标和隐私门

**Files:**
- Create: `server/platform/observability.py`
- Modify: `server/main.py`
- Create: `tests/v2/test_observability.py`
- Create: `tests/v2/test_log_privacy.py`

- [ ] **Step 1: 写请求 ID 和日志隐私测试**

```python
from __future__ import annotations


async def test_request_id_is_returned(v2_client, org_api_key) -> None:
    response = await v2_client.get(
        "/api/v2/tenancy/me",
        headers={"X-API-Key": org_api_key, "X-Request-ID": "req-test-001"},
    )
    assert response.headers["X-Request-ID"] == "req-test-001"


async def test_contract_text_is_not_logged(v2_client, org_api_key, caplog) -> None:
    secret_text = "本合同高度敏感且不可进入日志"
    await v2_client.post(
        "/api/v2/contracts",
        headers={"X-API-Key": org_api_key, "Idempotency-Key": "privacy-001"},
        json={"title": "隐私测试", "contract_type": "other", "text_content": secret_text},
    )
    assert secret_text not in caplog.text
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `pytest tests/v2/test_observability.py tests/v2/test_log_privacy.py -q`
Expected: FAIL，因为请求 ID 中间件尚未注册。

- [ ] **Step 3: 实现可观测入口**

`configure_observability(app)` 完成：

- 接收合法 `X-Request-ID`，否则生成 UUID；
- 把 request ID 写入 `contextvars.ContextVar`；
- 返回头包含相同 request ID；
- 记录 method、route template、status、duration_ms、organization_id；
- `/metrics` 暴露请求数、时延、任务数、任务失败数；
- `OTEL_ENABLED=true` 时启用 FastAPI instrumentation 和 OTLP HTTP exporter；
- 任何 span attribute 都不能包含请求体、合同正文、Prompt、模型响应或 API Key。

核心中间件：

```python
@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    incoming = request.headers.get("X-Request-ID", "")
    request_id = incoming if REQUEST_ID_PATTERN.fullmatch(incoming) else uuid.uuid4().hex
    token = request_id_var.set(request_id)
    started = time.perf_counter()
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        route = request.scope.get("route")
        route_path = getattr(route, "path", "unmatched")
        REQUEST_DURATION.labels(request.method, route_path).observe(
            time.perf_counter() - started
        )
        return response
    finally:
        request_id_var.reset(token)
```

路由不存在时使用 `"unmatched"` 标签，避免 `None.path`。

- [ ] **Step 4: 验证并提交**

Run: `pytest tests/v2/test_observability.py tests/v2/test_log_privacy.py -q`
Expected: request ID、指标标签基数和隐私测试全部通过。

```powershell
git add server/platform/observability.py server/main.py tests/v2/test_observability.py tests/v2/test_log_privacy.py
git commit -m ":chart_with_upwards_trend: ai-feat(新增) 增加链路追踪与隐私指标"
```

## Task 12：交付 Docker Compose、CI 和 M0 验收脚本

**Files:**
- Modify: `docker/Dockerfile`
- Modify: `docker/docker-compose.yml`
- Create: `.github/workflows/ci.yml`
- Create: `scripts/verify_m0.py`
- Create: `tests/integration/test_m0_smoke.py`
- Modify: `README.md`
- Modify: `docs/TECHNICAL.md`

- [ ] **Step 1: 写端到端冒烟测试**

```python
from __future__ import annotations

import asyncio

import httpx


async def main() -> None:
    async with httpx.AsyncClient(base_url="http://localhost:8080", timeout=30) as client:
        health = await client.get("/health")
        health.raise_for_status()
        assert health.json()["database"] == "ready"
        assert health.json()["redis"] == "ready"


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: 更新容器拓扑**

`docker/docker-compose.yml` 定义以下服务和健康依赖：

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: clauselight
      POSTGRES_USER: clauselight
      POSTGRES_PASSWORD: clauselight
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U clauselight -d clauselight"]
      interval: 5s
      timeout: 3s
      retries: 20
  redis:
    image: redis:7-alpine
    command: ["redis-server", "--appendonly", "no"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 20
  migrate:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    command: ["alembic", "upgrade", "head"]
    depends_on:
      postgres:
        condition: service_healthy
  api:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    command: ["python", "-m", "server.main"]
    ports: ["8080:8080"]
    depends_on:
      migrate:
        condition: service_completed_successfully
      redis:
        condition: service_healthy
  worker:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    command: ["python", "-m", "server.workers.main"]
    depends_on:
      migrate:
        condition: service_completed_successfully
      redis:
        condition: service_healthy
```

通过 Compose `environment` 注入 `DATABASE_URL`、`REDIS_URL`、`REDIS_REQUIRED=true` 和测试专用 `AUTH_PEPPER`。PostgreSQL 数据使用命名卷；Redis 数据可重建，不挂持久卷。

- [ ] **Step 3: 建立 CI 门**

`.github/workflows/ci.yml` 在 Python 3.10、3.11、3.12 上运行 Ruff 和 SQLite 单元测试；在 Python 3.11 job 中启动 PostgreSQL 16 与 Redis 7，执行：

```powershell
alembic upgrade head
pytest tests/v2 tests/integration -q -m "not ocr_integration"
python -m ruff check server tests scripts
```

OCR 真实测试放在手动触发的 `ocr-runtime` job，固定使用 Python 3.10 和已锁定 Paddle 版本，避免每次 PR 重复下载模型。

- [ ] **Step 4: 实现 `verify_m0.py`**

脚本依次验证：

```text
1. 当前 Alembic revision 等于 head
2. PostgreSQL SELECT 1
3. Redis PING
4. 创建组织和 API Key
5. 调用 POST /api/v2/contracts 两次并验证幂等
6. Worker 完成 document.ingest 测试处理器
7. 查询任务最终状态和审计事件
8. 检查日志文件不包含合同样例正文
```

任一步失败返回非零退出码；成功输出 JSON，只包含状态、ID、耗时和计数。

- [ ] **Step 5: 文档化本地启动和迁移**

README 和 `docs/TECHNICAL.md` 必须给出：

```powershell
docker compose -f docker/docker-compose.yml up --build -d
docker compose -f docker/docker-compose.yml run --rm migrate
python scripts/verify_m0.py
python scripts/import_v1_sqlite.py --source data/clause_light.db --dry-run
```

同时说明 PostgreSQL/Redis/Kafka 的职责边界、v1 数据备份方法、回滚到 v1 分支的方法，以及 Kafka 不属于 M0 运行依赖。

- [ ] **Step 6: 执行完整验收**

Run: `pytest -q`
Expected: v1 与 v2 单元测试全部通过，无新增 warning。

Run: `python -m ruff check server tests scripts`
Expected: `All checks passed!`

Run: `docker compose -f docker/docker-compose.yml up --build -d`
Expected: `postgres`、`redis`、`api`、`worker` healthy/running，`migrate` exited 0。

Run: `python scripts/verify_m0.py`
Expected: JSON 中 `status` 为 `passed`、`duplicate_side_effects` 为 0、`privacy_violations` 为 0。

Run: `docker compose -f docker/docker-compose.yml down`
Expected: 停止 M0 容器；不使用 `-v`，保留 PostgreSQL 命名卷。

- [ ] **Step 7: 提交**

```powershell
git add docker .github/workflows/ci.yml scripts/verify_m0.py tests/integration/test_m0_smoke.py README.md docs/TECHNICAL.md
git commit -m ":white_check_mark: ai-feat(新增) 完成合同智能底座交付门"
```

## M0 完成定义

只有下列条件同时满足，M0 才能标记完成并进入 M1：

- [ ] `alembic upgrade head`、`downgrade base`、再次升级均通过；
- [ ] v1 全量回归、v2 单元/集成、租户隔离和故障恢复测试全部通过；
- [ ] Docker Compose 一条命令启动 API、Worker、PostgreSQL、Redis；
- [ ] Redis 断开不会丢失合同、任务最终状态、Outbox 或审计；
- [ ] 重复请求、Worker 崩溃和任务重试不产生重复副作用；
- [ ] OCR 固定样例真实运行通过；
- [ ] v1 SQLite dry-run 和正式导入报告计数守恒；
- [ ] 日志、Trace、指标不包含合同正文、Prompt、模型响应或凭据；
- [ ] README、TECHNICAL、API 文档和 ADR 与实现一致；
- [ ] 生成一份可用于简历的数据：迁移耗时、API P95、任务恢复率、重复副作用数和测试结果。

M0 不实现 pgvector、混合检索、Rerank、模型路由、Kafka 或真实电子签；它们分别进入 M1、M5 和 M3，避免底座阶段过度扩张。
