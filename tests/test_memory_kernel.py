"""MemoryKernel 门面测试"""

from __future__ import annotations

import pytest

from server.core.memory import store
from server.core.memory.adapters.noop import NoopTeamMemoryAdapter
from server.core.memory.kernel import MemoryKernel


@pytest.mark.asyncio
async def test_kernel_retrieve_after_seed(db_session):
    k = MemoryKernel(db_session, adapter=NoopTeamMemoryAdapter())
    sid = await k.start_session("c1", "劳动合同")
    await k.append_event(sid, "step", {"name": "ocr_done"})
    # 直接经 store 写入 active atom 已在 Task3 覆盖；此处 kernel.record_feedback 建 atom
    aid = await store.upsert_atom(
        db_session,
        {
            "content": "竞业限制补偿金低于月工资30%应标黄",
            "status": "active",
            "confidence": 0.9,
            "contract_type": "劳动合同",
        },
    )
    await db_session.commit()
    hits = await k.retrieve("竞业限制", contract_type="劳动合同")
    assert any("竞业" in h.text for h in hits)
    pushed = await k.adapter.push_assets([])
    assert pushed == 0
