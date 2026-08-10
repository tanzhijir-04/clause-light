"""资产分级生效与回滚审计测试"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from server.models.database import AssetAuditLog, KnowledgeRule


@pytest.mark.asyncio
async def test_high_confidence_auto_activates(db_session):
    """置信度达到阈值时应自动 active 并同步 is_active"""
    from server.core.distill import activate

    r = KnowledgeRule(
        id="r1",
        category="通用",
        rule_text="高置信规则",
        confidence=0.8,
        status="pending",
        is_active=False,
    )
    db_session.add(r)
    await db_session.commit()
    status = await activate.maybe_activate(db_session, "rule", "r1")
    await db_session.commit()
    assert status == "active"
    assert (await db_session.get(KnowledgeRule, "r1")).is_active is True

    # 应写入审计日志
    logs = (
        await db_session.execute(
            select(AssetAuditLog).where(AssetAuditLog.asset_id == "r1")
        )
    ).scalars().all()
    assert len(logs) >= 1
    assert logs[0].action == "activate"


@pytest.mark.asyncio
async def test_low_confidence_stays_pending(db_session):
    """低于阈值保持 pending"""
    from server.core.distill import activate

    r = KnowledgeRule(
        id="r_low",
        category="通用",
        rule_text="低置信规则",
        confidence=0.5,
        status="pending",
        is_active=False,
    )
    db_session.add(r)
    await db_session.commit()
    status = await activate.maybe_activate(db_session, "rule", "r_low")
    await db_session.commit()
    assert status == "pending"
    assert (await db_session.get(KnowledgeRule, "r_low")).is_active is False


@pytest.mark.asyncio
async def test_rollback_sets_rolled_back(db_session):
    """回滚将状态设为 rolled_back"""
    from server.core.distill import activate

    r = KnowledgeRule(
        id="r2",
        category="通用",
        rule_text="x",
        confidence=0.9,
        status="active",
        is_active=True,
    )
    db_session.add(r)
    await db_session.commit()
    await activate.rollback(db_session, "rule", "r2")
    await db_session.commit()
    assert (await db_session.get(KnowledgeRule, "r2")).status == "rolled_back"


@pytest.mark.asyncio
async def test_approve_and_reject(db_session):
    """人工审核通过/拒绝"""
    from server.core.distill import activate

    r = KnowledgeRule(
        id="r3",
        category="通用",
        rule_text="待审",
        confidence=0.4,
        status="pending",
        is_active=False,
    )
    db_session.add(r)
    await db_session.commit()

    await activate.approve(db_session, "rule", "r3")
    await db_session.commit()
    rule = await db_session.get(KnowledgeRule, "r3")
    assert rule.status == "active"
    assert rule.is_active is True

    await activate.reject(db_session, "rule", "r3")
    await db_session.commit()
    rule = await db_session.get(KnowledgeRule, "r3")
    assert rule.status == "disabled"
    assert rule.is_active is False
