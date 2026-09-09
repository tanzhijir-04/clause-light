"""Alembic 迁移环境。"""

from __future__ import annotations

import asyncio

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from server.config import settings
from server.models.base import Base
import server.models.database  # noqa: F401  注册 v1 metadata
import server.modules.audit.models  # noqa: F401  注册审计模型
import server.modules.contracts.models  # noqa: F401  注册合同模型
import server.modules.events.models  # noqa: F401  注册事件模型
import server.modules.jobs.models  # noqa: F401  注册任务模型
import server.modules.legacy_import.models  # noqa: F401  注册导入模型
import server.modules.tenancy.models  # noqa: F401  注册租户模型


config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """以离线模式生成迁移 SQL。"""
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """在同步连接回调中执行迁移。"""
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """创建异步引擎并运行迁移。"""
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
    asyncio.run(run_async_migrations())
