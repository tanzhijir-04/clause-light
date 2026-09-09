from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from server.models.base import Base
from server.modules.jobs.models import ProcessingJob
from server.modules.jobs.repository import JobRepository


@pytest.mark.integration
@pytest.mark.asyncio
async def test_two_postgres_workers_claim_one_job() -> None:
    database_url = os.getenv("INTEGRATION_DATABASE_URL")
    if not database_url:
        pytest.skip("未配置 INTEGRATION_DATABASE_URL")

    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    job_id = uuid.uuid4()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as session:
        session.add(
            ProcessingJob(
                id=job_id,
                organization_id=uuid.uuid4(),
                job_type="integration.claim",
                aggregate_type="test",
                aggregate_id=uuid.uuid4(),
                idempotency_key=uuid.uuid4().hex,
            )
        )
        await session.commit()

    async def claim(worker_id: str):
        async with factory() as session:
            job = await JobRepository(session).claim_next(worker_id, 60)
            await session.commit()
            return job.id if job is not None else None

    claimed = await asyncio.gather(claim("worker-a"), claim("worker-b"))
    assert [item for item in claimed if item is not None] == [job_id]

    async with factory() as session:
        await session.execute(delete(ProcessingJob).where(ProcessingJob.id == job_id))
        await session.commit()
    await engine.dispose()
