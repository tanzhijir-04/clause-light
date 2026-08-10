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


class BrokenLLM:
    """返回非法 JSON，用于软失败测试"""

    async def chat(self, messages, task="analysis", **kwargs):
        class R:
            content = "这不是合法 JSON {{{"

        return R()


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
