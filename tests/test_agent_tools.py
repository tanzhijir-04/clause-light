"""Agent 记忆/Wiki/Skill 工具包装测试"""

from __future__ import annotations

import pytest

from server.core.memory import store
from server.core.agent_tools import build_loadout, build_stage_context


@pytest.mark.asyncio
async def test_build_loadout_empty_db(db_session):
    """空库时 loadout 为空字符串或合法字符串（降级）"""
    text = await build_loadout(db_session, contract_type="租赁合同", query="租赁")
    assert text == "" or isinstance(text, str)


@pytest.mark.asyncio
async def test_build_stage_context_includes_atom(db_session):
    """有原子记忆或规则时，stage 上下文应包含相关内容"""
    await store.upsert_atom(
        db_session,
        {
            "content": "用户是乙方视角",
            "status": "active",
            "confidence": 0.9,
            "contract_type": "租赁合同",
        },
    )
    await db_session.commit()
    text = await build_stage_context(
        db_session,
        contract_type="租赁合同",
        query="租赁",
        kb_rules=["规则A"],
    )
    assert "乙方" in text or "规则A" in text
