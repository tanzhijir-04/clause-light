"""数据库引擎、Session 生命周期和健康检查。"""

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
    """在调用方控制的上下文中提交事务，异常时回滚。"""
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI 数据库依赖。"""
    async with session_scope() as session:
        yield session


async def database_is_ready(target_engine: AsyncEngine = engine) -> bool:
    """检查数据库是否可以执行最小查询。"""
    try:
        async with target_engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
