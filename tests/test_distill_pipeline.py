"""Distill Pipeline 测试 — 分析后提炼候选记忆资产"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from server.models.database import KnowledgeRule, MemoryAtom


class FakeLLM:
    """返回固定 JSON 的假 LLM"""

    async def chat(self, messages, task="analysis", **kwargs):
        class R:
            content = json.dumps(
                {
                    "atoms": [
                        {
                            "content": "用户拒绝异地仲裁",
                            "kind": "preference",
                            "confidence": 0.8,
                        }
                    ],
                    "rules": [
                        {
                            "rule_text": "争议解决地应在用户所在地",
                            "category": "通用",
                            "confidence": 0.7,
                            "trigger_keywords": ["仲裁"],
                        }
                    ],
                    "skills": [],
                    "wiki_patches": [],
                },
                ensure_ascii=False,
            )

        return R()

    async def chat_structured(self, messages, schema, task="analysis", **kwargs):
        from server.core.llm import LLMGateway, StructuredLLMResponse

        r = await self.chat(messages, task=task)
        gw = LLMGateway()
        gw._clients = {}
        parsed = gw._validate_schema(r.content, schema)
        return StructuredLLMResponse(
            content=r.content, parsed=parsed, via="fallback"
        )


class BrokenLLM:
    """返回非法 JSON，用于软失败测试"""

    async def chat(self, messages, task="analysis", **kwargs):
        class R:
            content = "这不是合法 JSON {{{"

        return R()

    async def chat_structured(self, messages, schema, task="analysis", **kwargs):
        from server.core.llm import StructuredLLMResponse

        r = await self.chat(messages, task=task)
        return StructuredLLMResponse(content=r.content, parsed=None, via="fallback")


@pytest.mark.asyncio
async def test_distill_creates_pending_and_active(db_session):
    """提炼应写入 atom/rule，并按置信度 maybe_activate"""
    from server.core.distill.pipeline import distill_from_analysis

    result = await distill_from_analysis(
        db_session,
        FakeLLM(),
        session_id="s1",
        contract_type="租赁合同",
        clause_summaries=[{"id": "9.1", "risk_level": "red", "issue": "异地仲裁"}],
    )
    await db_session.commit()
    assert result["atoms"] >= 1
    assert result["rules"] >= 1

    atoms = (await db_session.execute(select(MemoryAtom))).scalars().all()
    assert any("异地仲裁" in a.content for a in atoms)
    # confidence 0.8 >= 0.75 → active
    atom = next(a for a in atoms if "异地仲裁" in a.content)
    assert atom.status == "active"

    rules = (await db_session.execute(select(KnowledgeRule))).scalars().all()
    assert any("争议解决地" in r.rule_text for r in rules)
    # confidence 0.7 < 0.75 → pending
    rule = next(r for r in rules if "争议解决地" in r.rule_text)
    assert rule.status == "pending"


@pytest.mark.asyncio
async def test_distill_soft_fails_on_bad_json(db_session):
    """解析失败返回全 0，不抛异常"""
    from server.core.distill.pipeline import distill_from_analysis

    result = await distill_from_analysis(
        db_session,
        BrokenLLM(),
        session_id="s2",
        contract_type="租赁合同",
        clause_summaries=[],
    )
    assert result == {"rules": 0, "atoms": 0, "skills": 0, "wiki": 0}


@pytest.mark.asyncio
async def test_merge_does_not_demote_active_rule(db_session):
    """Distill 合并到已有 active 规则时不得降级 status"""
    from server.core.distill.pipeline import distill_from_analysis
    from server.core.knowledge import sync_rule_is_active

    rule = KnowledgeRule(
        id="merge_active",
        category="通用",
        rule_text="争议解决地应在用户所在地",
        confidence=0.8,
        source="auto_learned",
        status="active",
        is_active=True,
        confirm_count=1,
    )
    sync_rule_is_active(rule)
    db_session.add(rule)
    await db_session.commit()

    result = await distill_from_analysis(
        db_session,
        FakeLLM(),
        session_id="s_merge",
        contract_type="租赁合同",
        clause_summaries=[{"id": "9.1", "risk_level": "red", "issue": "异地仲裁"}],
    )
    await db_session.commit()
    assert result["rules"] >= 1

    merged = await db_session.get(KnowledgeRule, "merge_active")
    assert merged.status == "active"
    assert merged.is_active is True
    assert merged.confirm_count >= 2


@pytest.mark.asyncio
async def test_wiki_active_not_overwritten_by_distill(db_session):
    """Distill 遇到 active Wiki 时不得改写正文，应新建 pending 页"""
    from server.core.distill.pipeline import _upsert_wiki
    from server.models.database import WikiPage
    from sqlalchemy import select

    active = WikiPage(
        id="wiki_active_1",
        slug="lease-deposit",
        title="押金说明",
        body="线上正文，勿覆盖",
        status="active",
        source="manual",
        confidence=1.0,
    )
    db_session.add(active)
    await db_session.commit()

    new_id = await _upsert_wiki(
        db_session,
        {
            "slug": "lease-deposit",
            "title": "押金说明（修订）",
            "body": "蒸馏产生的新正文",
            "confidence": 0.9,
        },
    )
    await db_session.commit()
    assert new_id is not None
    assert new_id != "wiki_active_1"

    original = await db_session.get(WikiPage, "wiki_active_1")
    assert original.status == "active"
    assert original.body == "线上正文，勿覆盖"
    assert original.slug == "lease-deposit"

    pending = await db_session.get(WikiPage, new_id)
    assert pending is not None
    assert pending.status == "pending"
    assert pending.body == "蒸馏产生的新正文"
    assert pending.slug.startswith("lease-deposit-pending-")

    pages = (await db_session.execute(select(WikiPage))).scalars().all()
    assert len(pages) == 2
