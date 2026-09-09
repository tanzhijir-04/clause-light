from __future__ import annotations

import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from server.models.base import Base
from server.modules.jobs.models import ProcessingJob
from server.modules.tenancy.auth import digest_api_key
from server.modules.tenancy.models import ApiCredential, Organization
from server.platform.database import get_db


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


@pytest_asyncio.fixture
async def org_api_key(v2_session: AsyncSession) -> str:
    organization = Organization(name="Test Organization", slug=uuid.uuid4().hex)
    v2_session.add(organization)
    await v2_session.flush()
    secret = "cl_live_" + uuid.uuid4().hex
    v2_session.add(
        ApiCredential(
            organization_id=organization.id,
            name="test credential",
            key_prefix=secret[:16],
            key_digest=digest_api_key(secret, "development-only-change-me"),
        )
    )
    await v2_session.flush()
    return secret


@pytest_asyncio.fixture
async def v2_client(v2_session: AsyncSession):
    from server.main import app

    async def override_get_db():
        yield v2_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_db, None)
