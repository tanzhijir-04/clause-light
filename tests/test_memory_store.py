"""MemoryStore 写入与反馈测试"""

import pytest
from server.core.memory import store


@pytest.mark.asyncio
async def test_session_event_atom_flow(db_session):
    sid = await store.start_session(db_session, contract_id="c1", contract_type="租赁合同")
    eid = await store.append_event(
        db_session, sid, "feedback", {"clause_id": "8.1", "from": "yellow", "to": "red"}
    )
    aid = await store.upsert_atom(
        db_session,
        {
            "content": "条款违约金偏高时应标红",
            "kind": "preference",
            "session_id": sid,
            "contract_type": "租赁合同",
            "confidence": 0.6,
            "status": "pending",
        },
    )
    await db_session.commit()
    assert sid and eid and aid
    atom = await store.apply_feedback(db_session, aid, confirm=True)
    await db_session.commit()
    assert atom.confirm_count == 1
    assert atom.confidence >= 0.6
