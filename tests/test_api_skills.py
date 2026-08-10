"""Skill 资产 API 测试"""

from __future__ import annotations

from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from server.models.database import get_db


@pytest_asyncio.fixture
async def skills_client() -> AsyncGenerator[AsyncClient, None]:
    """仅挂载 skills 路由，避免 main 可选依赖干扰"""
    from fastapi import FastAPI

    from server.api.skills import router
    from tests.conftest import override_get_db

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_and_match_skill(skills_client, db_session):
    r = await skills_client.post(
        "/api/skills",
        json={
            "name": "装修付款审查",
            "triggers": {"contract_types": ["装修合同"], "keywords": ["付款"]},
            "steps": ["核对付款节点与验收绑定"],
            "validation": [],
            "confidence": 0.9,
            "status": "active",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "装修付款审查"
    assert body["status"] == "active"

    m = await skills_client.get(
        "/api/skills/match",
        params={"contract_type": "装修合同", "q": "进度款付款"},
    )
    assert m.status_code == 200
    assert len(m.json()) >= 1
    assert m.json()[0]["name"] == "装修付款审查"


@pytest.mark.asyncio
async def test_match_ignores_pending(skills_client, db_session):
    await skills_client.post(
        "/api/skills",
        json={
            "name": "待审Skill",
            "triggers": {"contract_types": ["租赁合同"], "keywords": ["租金"]},
            "steps": ["检查租金条款"],
            "confidence": 0.5,
            "status": "pending",
        },
    )
    m = await skills_client.get(
        "/api/skills/match",
        params={"contract_type": "租赁合同", "q": "租金支付"},
    )
    assert m.status_code == 200
    assert m.json() == []


@pytest.mark.asyncio
async def test_list_skills(skills_client, db_session):
    await skills_client.post(
        "/api/skills",
        json={
            "name": "列表Skill",
            "triggers": {},
            "steps": ["step1"],
            "status": "active",
        },
    )
    listed = await skills_client.get("/api/skills")
    assert listed.status_code == 200
    assert len(listed.json()) >= 1
