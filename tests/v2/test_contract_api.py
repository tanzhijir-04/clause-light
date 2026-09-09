from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_create_contract_returns_version_and_job(v2_client, org_api_key) -> None:
    response = await v2_client.post(
        "/api/v2/contracts",
        headers={"X-API-Key": org_api_key, "Idempotency-Key": "contract-001"},
        json={
            "title": "采购框架合同",
            "contract_type": "procurement",
            "text_content": "第一条 合同标的",
        },
    )
    assert response.status_code == 202
    body = response.json()
    assert set(body) == {"contract_id", "version_id", "job_id", "status"}
    assert body["status"] == "queued"


@pytest.mark.asyncio
async def test_create_contract_requires_idempotency_key(v2_client, org_api_key) -> None:
    response = await v2_client.post(
        "/api/v2/contracts",
        headers={"X-API-Key": org_api_key},
        json={"title": "合同", "contract_type": "other", "text_content": "正文"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_contract_and_versions_are_queryable(v2_client, org_api_key) -> None:
    created = await v2_client.post(
        "/api/v2/contracts",
        headers={"X-API-Key": org_api_key, "Idempotency-Key": "contract-query-001"},
        json={"title": "查询合同", "contract_type": "other", "text_content": "正文"},
    )
    body = created.json()
    contract = await v2_client.get(
        f"/api/v2/contracts/{body['contract_id']}",
        headers={"X-API-Key": org_api_key},
    )
    versions = await v2_client.get(
        f"/api/v2/contracts/{body['contract_id']}/versions",
        headers={"X-API-Key": org_api_key},
    )
    assert contract.status_code == 200
    assert contract.json()["id"] == body["contract_id"]
    assert versions.status_code == 200
    assert len(versions.json()) == 1
