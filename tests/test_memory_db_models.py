"""L0–L3 记忆数据表模型测试"""

import pytest
from server.models.database import (
    MemorySession,
    MemoryEvent,
    MemoryAtom,
    MemoryScenario,
    MemoryPersona,
)


@pytest.mark.asyncio
async def test_create_session_and_atom(db_session):
    s = MemorySession(id="sess1", contract_id="c1", contract_type="租赁合同")
    db_session.add(s)
    a = MemoryAtom(
        id="atom1",
        session_id="sess1",
        content="用户偏好：违约金超过20%标红",
        kind="preference",
        confidence=0.8,
        status="active",
    )
    db_session.add(a)
    await db_session.commit()
    assert (await db_session.get(MemoryAtom, "atom1")).kind == "preference"
