"""记忆资产待审 / 回滚 API 测试"""

from __future__ import annotations

from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from server.models.database import KnowledgeRule, get_db


@pytest_asyncio.fixture
async def pending_client() -> AsyncGenerator[AsyncClient, None]:
    """仅挂载 memory 路由"""
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
async def test_pending_approve_rule(pending_client, db_session):
    db_session.add(
        KnowledgeRule(
            id="rp1",
            category="通用",
            rule_text="待审违约金规则",
            confidence=0.5,
            status="pending",
            is_active=False,
        )
    )
    await db_session.commit()

    listed = await pending_client.get("/api/memory/pending")
    assert listed.status_code == 200
    assert any(i["id"] == "rp1" for i in listed.json())

    ok = await pending_client.post("/api/memory/pending/rule/rp1/approve")
    assert ok.status_code == 200

    # 刷新会话以看到 API 提交的变更
    await db_session.refresh(
        await db_session.get(KnowledgeRule, "rp1")
    )
    rule = await db_session.get(KnowledgeRule, "rp1")
    assert rule is not None
    assert rule.status == "active"
    assert rule.is_active is True

    from server.core.knowledge import KnowledgeEngine

    hits = await KnowledgeEngine(db_session).search("违约金", "其他")
    assert any("待审违约金" in h for h in hits)


@pytest.mark.asyncio
async def test_pending_reject_and_rollback(pending_client, db_session):
    db_session.add(
        KnowledgeRule(
            id="rp2",
            category="通用",
            rule_text="可拒绝规则",
            confidence=0.4,
            status="pending",
            is_active=False,
        )
    )
    db_session.add(
        KnowledgeRule(
            id="rp3",
            category="通用",
            rule_text="可回滚规则",
            confidence=0.9,
            status="active",
            is_active=True,
        )
    )
    await db_session.commit()

    rej = await pending_client.post("/api/memory/pending/rule/rp2/reject")
    assert rej.status_code == 200
    rolled = await pending_client.post("/api/memory/pending/rule/rp3/rollback")
    assert rolled.status_code == 200

    r2 = await db_session.get(KnowledgeRule, "rp2")
    r3 = await db_session.get(KnowledgeRule, "rp3")
    await db_session.refresh(r2)
    await db_session.refresh(r3)
    assert r2.status == "disabled"
    assert r3.status == "rolled_back"
