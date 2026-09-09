from __future__ import annotations

from contextlib import asynccontextmanager

import pytest

from server.workers.errors import RetryableJobError
from server.workers.main import HANDLERS, register_handler, run_once


@pytest.mark.asyncio
async def test_retryable_worker_failure_returns_job_to_queue(v2_session, queued_job, monkeypatch) -> None:
    async def handler(job, session) -> None:
        raise RetryableJobError("TEMPORARY_PROVIDER")

    job_type = "test.retryable"
    register_handler(job_type, handler)
    queued_job.job_type = job_type
    await v2_session.flush()

    @asynccontextmanager
    async def fake_session_scope():
        yield v2_session

    monkeypatch.setattr("server.workers.main.session_scope", fake_session_scope)
    assert await run_once("worker-1") is True
    assert queued_job.status == "queued"
    assert queued_job.last_error_code == "TEMPORARY_PROVIDER"
