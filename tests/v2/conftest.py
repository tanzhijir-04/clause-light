from __future__ import annotations

import uuid

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from server.models.base import Base
from server.modules.jobs.models import ProcessingJob


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


@pytest_asyncio.fixture
async def queued_job(v2_session: AsyncSession) -> ProcessingJob:
    job = ProcessingJob(
        organization_id=uuid.uuid4(),
        job_type="document.ingest",
        aggregate_type="contract_version",
        aggregate_id=uuid.uuid4(),
        idempotency_key=uuid.uuid4().hex,
    )
    v2_session.add(job)
    await v2_session.flush()
    return job
