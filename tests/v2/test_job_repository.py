from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from server.modules.jobs.repository import JobRepository


@pytest.mark.asyncio
async def test_expired_lease_can_be_reclaimed(v2_session, queued_job) -> None:
    queued_job.status = "running"
    queued_job.lease_owner = "dead-worker"
    queued_job.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await v2_session.flush()

    claimed = await JobRepository(v2_session).claim_next(
        worker_id="replacement-worker",
        lease_seconds=60,
    )
    assert claimed is not None
    assert claimed.id == queued_job.id
    assert claimed.lease_owner == "replacement-worker"
    assert claimed.attempts == 1


@pytest.mark.asyncio
async def test_complete_step_is_idempotent(v2_session, queued_job) -> None:
    repository = JobRepository(v2_session)
    first = await repository.complete_step(queued_job, "document.ingest", {"ok": True})
    second = await repository.complete_step(queued_job, "document.ingest", {"ok": False})

    assert first.id == second.id
    assert second.output_json == {"ok": True}
