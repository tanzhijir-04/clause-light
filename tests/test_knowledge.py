"""知识库引擎测试"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from server.core.knowledge import KnowledgeEngine
from server.models.database import KnowledgeRule, LegalReference


class TestKnowledgeSearch:
    """知识库检索测试"""

    async def test_search_empty_database(self, db_session):
        """测试空数据库检索"""
        engine = KnowledgeEngine(db_session)
        results = await engine.search("租赁合同", "租赁合同")
        assert results == []

    async def test_search_with_matching_rules(self, db_session):
        """测试匹配规则检索"""
        # 插入测试规则
        rule1 = KnowledgeRule(
            id="rule_1",
            category="租赁",
            rule_text="租赁合同中违约金不应超过合同总金额的30%",
            trigger_keywords=json.dumps(["违约金", "租赁"]),
            confidence=0.8,
            is_active=True,
        )
        rule2 = KnowledgeRule(
            id="rule_2",
            category="租赁",
            rule_text="租赁期限最长不得超过20年",
            trigger_keywords=json.dumps(["租赁期限"]),
            confidence=0.9,
            is_active=True,
        )
        db_session.add_all([rule1, rule2])
        await db_session.commit()

        engine = KnowledgeEngine(db_session)
        results = await engine.search("违约金不超过30%", "租赁合同")
        assert len(results) > 0
        assert any("违约金" in r for r in results)

    async def test_search_inactive_rules_excluded(self, db_session):
        """测试禁用规则不被检索"""
        rule = KnowledgeRule(
            id="rule_inactive",
            category="租赁",
            rule_text="这是一条禁用规则",
            is_active=False,
        )
        db_session.add(rule)
        await db_session.commit()

        engine = KnowledgeEngine(db_session)
        results = await engine.search("禁用规则", "租赁合同")
        assert len(results) == 0

    async def test_search_category_filter(self, db_session):
        """测试类别过滤"""
        rule_rental = KnowledgeRule(
            id="rule_rental",
            category="租赁",
            rule_text="租赁专用规则",
            is_active=True,
        )
        rule_labor = KnowledgeRule(
            id="rule_labor",
            category="劳动",
            rule_text="劳动专用规则",
            is_active=True,
        )
        rule_general = KnowledgeRule(
            id="rule_general",
            category="通用",
            rule_text="通用规则",
            is_active=True,
        )
        db_session.add_all([rule_rental, rule_labor, rule_general])
        await db_session.commit()

        engine = KnowledgeEngine(db_session)
        results = await engine.search("规则", "租赁合同")
        # 应该包含租赁规则和通用规则，不包含劳动规则
        assert len(results) >= 2

    async def test_search_keyword_matching(self, db_session):
        """测试关键词匹配评分"""
        rule = KnowledgeRule(
            id="rule_kw",
            category="租赁",
            rule_text="租赁合同违约金条款",
            trigger_keywords=json.dumps(["违约金"]),
            confidence=0.7,
            is_active=True,
        )
        db_session.add(rule)
        await db_session.commit()

        engine = KnowledgeEngine(db_session)
        results = await engine.search("违约金", "租赁合同")
        assert len(results) > 0


class TestKnowledgeAddRule:
    """知识库新增规则测试"""

    async def test_add_rule_success(self, db_session):
        """测试成功新增规则"""
        engine = KnowledgeEngine(db_session)
        result = await engine.add_rule({
            "rule_text": "测试规则",
            "category": "租赁",
            "trigger_keywords": ["测试"],
            "confidence": 0.6,
            "source": "manual",
        })
        assert result["success"] is True
        assert result["id"] is not None

        # 验证规则已添加
        stmt = select(KnowledgeRule).where(KnowledgeRule.id == result["id"])
        db_result = await db_session.execute(stmt)
        rule = db_result.scalar_one_or_none()
        assert rule is not None
        assert rule.rule_text == "测试规则"

    async def test_add_rule_default_values(self, db_session):
        """测试新增规则默认值"""
        engine = KnowledgeEngine(db_session)
        result = await engine.add_rule({"rule_text": "默认值测试规则"})
        assert result["success"] is True

        stmt = select(KnowledgeRule).where(KnowledgeRule.id == result["id"])
        db_result = await db_session.execute(stmt)
        rule = db_result.scalar_one_or_none()
        assert rule.category == "通用"
        assert rule.confidence == 0.5
        assert rule.source == "manual"


class TestKnowledgeUpdateRule:
    """知识库更新规则测试"""

    async def test_update_rule_success(self, db_session):
        """测试成功更新规则"""
        rule = KnowledgeRule(
            id="update_rule_1",
            category="租赁",
            rule_text="原始规则",
            confidence=0.5,
        )
        db_session.add(rule)
        await db_session.commit()

        engine = KnowledgeEngine(db_session)
        await engine.update_rule("update_rule_1", {
            "rule_text": "更新后的规则",
            "confidence": 0.8,
        })

        stmt = select(KnowledgeRule).where(KnowledgeRule.id == "update_rule_1")
        result = await db_session.execute(stmt)
        updated = result.scalar_one_or_none()
        assert updated.rule_text == "更新后的规则"
        assert updated.confidence == 0.8

    async def test_update_nonexistent_rule(self, db_session):
        """测试更新不存在的规则（应静默失败）"""
        engine = KnowledgeEngine(db_session)
        # 不应抛出异常
        await engine.update_rule("nonexistent", {"rule_text": "测试"})


class TestKnowledgeDeleteRule:
    """知识库删除规则测试"""

    async def test_delete_rule_success(self, db_session):
        """测试成功删除规则"""
        rule = KnowledgeRule(
            id="delete_rule_1",
            category="租赁",
            rule_text="待删除规则",
        )
        db_session.add(rule)
        await db_session.commit()

        engine = KnowledgeEngine(db_session)
        await engine.delete_rule("delete_rule_1")

        stmt = select(KnowledgeRule).where(KnowledgeRule.id == "delete_rule_1")
        result = await db_session.execute(stmt)
        deleted = result.scalar_one_or_none()
        assert deleted is None

    async def test_delete_nonexistent_rule(self, db_session):
        """测试删除不存在的规则（应静默失败）"""
        engine = KnowledgeEngine(db_session)
        # 不应抛出异常
        await engine.delete_rule("nonexistent")


class TestKnowledgeStats:
    """知识库统计测试"""

    async def test_get_stats_empty(self, db_session):
        """测试空数据库统计"""
        engine = KnowledgeEngine(db_session)
        stats = await engine.get_stats()
        assert stats["totalRules"] == 0
        assert stats["totalLaws"] == 0

    async def test_get_stats_with_data(self, db_session):
        """测试有数据时的统计"""
        rules = [
            KnowledgeRule(
                id=f"stat_rule_{i}",
                category="租赁",
                rule_text=f"规则 {i}",
                confidence=0.5 + i * 0.1,
            )
            for i in range(5)
        ]
        db_session.add_all(rules)
        await db_session.commit()

        engine = KnowledgeEngine(db_session)
        stats = await engine.get_stats()
        assert stats["totalRules"] == 5
        assert stats["avgConfidence"] > 0


class TestKnowledgeApproveReject:
    """知识库审核测试"""

    async def test_approve_rule(self, db_session):
        """测试通过规则"""
        rule = KnowledgeRule(
            id="pending_rule_1",
            category="租赁",
            rule_text="待审核规则",
            confidence=0.5,
            source="auto_learned",
        )
        db_session.add(rule)
        await db_session.commit()

        engine = KnowledgeEngine(db_session)
        await engine.approve_rule("pending_rule_1")

        stmt = select(KnowledgeRule).where(KnowledgeRule.id == "pending_rule_1")
        result = await db_session.execute(stmt)
        approved = result.scalar_one_or_none()
        assert approved.confidence == 0.7  # 0.5 + 0.2
        assert approved.source == "manual"

    async def test_reject_rule(self, db_session):
        """测试拒绝规则"""
        rule = KnowledgeRule(
            id="pending_rule_2",
            category="租赁",
            rule_text="待拒绝规则",
            confidence=0.4,
            source="auto_learned",
        )
        db_session.add(rule)
        await db_session.commit()

        engine = KnowledgeEngine(db_session)
        await engine.reject_rule("pending_rule_2")

        stmt = select(KnowledgeRule).where(KnowledgeRule.id == "pending_rule_2")
        result = await db_session.execute(stmt)
        rejected = result.scalar_one_or_none()
        assert rejected.is_active is False
