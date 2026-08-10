"""分层记忆 REST API 测试"""

from __future__ import annotations

from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from server.core.memory import store
from server.models.database import get_db


@pytest_asyncio.fixture
async def memory_client() -> AsyncGenerator[AsyncClient, None]:
    """仅挂载 memory 路由，避免 server.main 依赖 qrcode 等可选包"""
    from fastapi import FastAPI

    from server.api.memory import router
    from tests.conftest import override_get_db

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_session_and_list_atoms(memory_client, db_session):
    r = await memory_client.post(
        "/api/memory/sessions",
        json={"contract_id": "c1", "contract_type": "租赁合同"},
    )
    assert r.status_code == 200
    sid = r.json()["id"]
    assert sid

    await store.upsert_atom(
        db_session,
        {
            "content": "测试原子",
            "status": "active",
            "confidence": 0.9,
            "contract_type": "租赁合同",
        },
    )
    await db_session.commit()
    r2 = await memory_client.get("/api/memory/atoms", params={"q": "原子"})
    assert r2.status_code == 200
    assert len(r2.json()) >= 1


@pytest.mark.asyncio
async def test_feedback_endpoint(memory_client, db_session):
    aid = await store.upsert_atom(
        db_session,
        {
            "content": "可反馈原子",
            "status": "active",
            "confidence": 0.5,
        },
    )
    await db_session.commit()
    r = await memory_client.post(
        "/api/memory/feedback",
        json={
            "atom_id": aid,
            "confirm": True,
            "payload": {"note": "正确"},
        },
    )
    assert r.status_code == 200
    assert r.json()["success"] is True
