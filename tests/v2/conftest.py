from __future__ import annotations

import uuid
import sqlite3

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


@pytest_asyncio.fixture
def v1_sqlite_path(tmp_path):
    path = tmp_path / "v1.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE contracts (
            id VARCHAR PRIMARY KEY,
            title VARCHAR NOT NULL,
            type VARCHAR NOT NULL,
            source_file VARCHAR,
            ocr_text TEXT,
            ocr_raw TEXT,
            created_at DATETIME,
            updated_at DATETIME
        );
        CREATE TABLE analyses (
            id VARCHAR PRIMARY KEY,
            contract_id VARCHAR NOT NULL,
            model_used VARCHAR,
            overall_score INTEGER,
            summary TEXT,
            recommendation VARCHAR,
            raw_result TEXT,
            source VARCHAR,
            created_at DATETIME,
            status VARCHAR,
            review_required BOOLEAN,
            review_reason TEXT,
            processing_mode VARCHAR
        );
        CREATE TABLE clause_analyses (
            id VARCHAR PRIMARY KEY,
            analysis_id VARCHAR NOT NULL,
            clause_number VARCHAR,
            clause_title VARCHAR,
            clause_content TEXT,
            risk_level VARCHAR,
            risk_type VARCHAR,
            risk_summary TEXT,
            plain_explanation TEXT,
            legal_basis TEXT,
            severity_score INTEGER,
            suggested_clause TEXT,
            can_negotiate BOOLEAN,
            user_feedback VARCHAR,
            created_at DATETIME,
            analysis_status VARCHAR,
            review_required BOOLEAN,
            review_reason TEXT,
            source_start INTEGER,
            source_end INTEGER,
            citation_ids TEXT
        );
        INSERT INTO contracts(id, title, type, ocr_text) VALUES
            ('legacy-contract-1', '采购合同', '采购合同', '正文不会进入拒绝报告');
        INSERT INTO analyses(id, contract_id, summary) VALUES
            ('legacy-analysis-1', 'legacy-contract-1', '摘要');
        INSERT INTO clause_analyses(id, analysis_id, clause_number, clause_content) VALUES
            ('legacy-clause-1', 'legacy-analysis-1', '第一条', '条款正文');
        INSERT INTO analyses(id, contract_id, summary) VALUES
            ('legacy-analysis-bad', 'missing-contract', '错误摘要');
        """
    )
    connection.commit()
    connection.close()
    return path
