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
