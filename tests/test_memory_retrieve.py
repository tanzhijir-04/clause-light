"""分层记忆召回与字符预算测试"""

from __future__ import annotations

import pytest

from server.core.memory import store
from server.core.memory.models import RetrieveBudget
from server.core.memory.retrieve import retrieve


@pytest.mark.asyncio
async def test_retrieve_respects_char_budget(db_session):
    for i in range(10):
        await store.upsert_atom(
            db_session,
            {
                "content": ("违约金偏好-" + str(i)) * 40,  # 较长文本
                "kind": "preference",
                "contract_type": "租赁合同",
                "confidence": 0.9,
                "status": "active",
            },
        )
    await db_session.commit()
    budget = RetrieveBudget(max_chars=200, max_l1=8, max_l2=0, max_l3=0)
    hits = await retrieve(db_session, "违约金", contract_type="租赁合同", budget=budget)
    assert sum(h.chars() for h in hits) <= 200
    assert all(h.layer == "l1" for h in hits)


@pytest.mark.asyncio
async def test_retrieve_ignores_pending(db_session):
    await store.upsert_atom(
        db_session,
        {
            "content": "不应被召回的 pending",
            "status": "pending",
            "confidence": 0.9,
            "contract_type": "租赁合同",
        },
    )
    await db_session.commit()
    hits = await retrieve(db_session, "pending", contract_type="租赁合同")
    assert hits == []
