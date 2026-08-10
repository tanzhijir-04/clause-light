"""资产表模型测试 — Skill / Wiki / Audit"""

from __future__ import annotations

import pytest

from server.models.database import AssetAuditLog, Skill, WikiLink, WikiPage


@pytest.mark.asyncio
async def test_skill_wiki_audit_models(db_session):
    """可创建 Skill、WikiPage、WikiLink、AssetAuditLog 并持久化"""
    db_session.add(Skill(
        id="sk1",
        name="装修付款审查",
        version=1,
        status="pending",
        triggers='{"contract_types":["装修合同"],"keywords":["付款"]}',
        steps='["核对付款节点"]',
        validation='[]',
        resources='[]',
        confidence=0.6,
    ))
    db_session.add(WikiPage(
        id="w1",
        slug="civil-code-584",
        title="民法典584条",
        body="...",
        status="active",
    ))
    db_session.add(WikiLink(
        id="l1",
        from_page_id="w1",
        to_page_id="w1",
        rel="related",
    ))
    db_session.add(AssetAuditLog(
        id="au1",
        asset_type="skill",
        asset_id="sk1",
        action="create",
        detail="{}",
    ))
    await db_session.commit()

    assert await db_session.get(Skill, "sk1") is not None
    assert await db_session.get(WikiPage, "w1") is not None
    assert await db_session.get(WikiLink, "l1") is not None
    assert await db_session.get(AssetAuditLog, "au1") is not None
