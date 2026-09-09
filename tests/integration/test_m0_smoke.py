from __future__ import annotations

import os

import httpx
import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_m0_service_health() -> None:
    base_url = os.getenv("M0_BASE_URL")
    if not base_url:
        pytest.skip("set M0_BASE_URL to run the Docker M0 smoke test")
    async with httpx.AsyncClient(base_url=base_url, timeout=30) as client:
        response = await client.get("/health")
        response.raise_for_status()
        health = response.json()
        assert health["database"] == "ready"
        assert health["redis"] == "ready"
