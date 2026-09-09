from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_job_can_be_read_canceled_and_its_events_listed(v2_client, org_api_key) -> None:
    created = await v2_client.post(
        "/api/v2/contracts",
        headers={"X-API-Key": org_api_key, "Idempotency-Key": "job-api-001"},
        json={"title": "任务合同", "contract_type": "other", "text_content": "正文"},
    )
    body = created.json()
    headers = {"X-API-Key": org_api_key}

    job = await v2_client.get(f"/api/v2/jobs/{body['job_id']}", headers=headers)
    events = await v2_client.get(f"/api/v2/jobs/{body['job_id']}/events", headers=headers)
    canceled = await v2_client.post(f"/api/v2/jobs/{body['job_id']}/cancel", headers=headers)

    assert job.status_code == 200
    assert job.json()["status"] == "queued"
    assert events.status_code == 200
    assert events.json()["events"] == []
    assert canceled.status_code == 200
    assert canceled.json()["status"] == "canceled"
