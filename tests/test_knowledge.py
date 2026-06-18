"""知识库引擎测试"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from server.core.knowledge import KnowledgeEngine
from server.models.database import (
    Analysis,
    ClauseAnalysis,
    Contract,
    KnowledgeRule,
    LegalReference,
)


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

    async def test_search_no_match(self, db_session):
        """测试无匹配规则"""
        rule = KnowledgeRule(
            id="rule_no_match",
            category="租赁",
            rule_text="租赁合同规则",
            confidence=0.7,
            is_active=True,
        )
        db_session.add(rule)
        await db_session.commit()

        engine = KnowledgeEngine(db_session)
        results = await engine.search("完全不相关的查询", "劳动")
        assert len(results) == 0

    async def test_search_top_k_limit(self, db_session):
        """测试 top_k 限制"""
        rules = [
            KnowledgeRule(
                id=f"rule_{i}",
                category="通用",
                rule_text=f"通用规则 {i}",
                confidence=0.5 + i * 0.05,
                is_active=True,
            )
            for i in range(10)
        ]
        db_session.add_all(rules)
        await db_session.commit()

        engine = KnowledgeEngine(db_session)
        results = await engine.search("规则", "其他", top_k=3)
        assert len(results) <= 3

    async def test_search_usage_count_increment(self, db_session):
        """测试搜索后使用次数递增"""
        rule = KnowledgeRule(
            id="rule_usage",
            category="租赁",
            rule_text="测试使用次数",
            usage_count=0,
            is_active=True,
        )
        db_session.add(rule)
        await db_session.commit()

        engine = KnowledgeEngine(db_session)
        await engine.search("测试使用次数", "租赁合同")

        stmt = select(KnowledgeRule).where(KnowledgeRule.id == "rule_usage")
        result = await db_session.execute(stmt)
        updated = result.scalar_one_or_none()
        assert updated.usage_count == 1

    async def test_search_general_always_included(self, db_session):
        """测试通用规则始终包含"""
        rule_general = KnowledgeRule(
            id="rule_gen",
            category="通用",
            rule_text="通用规则",
            is_active=True,
        )
        rule_labor = KnowledgeRule(
            id="rule_labor2",
            category="劳动",
            rule_text="劳动规则",
            is_active=True,
        )
        db_session.add_all([rule_general, rule_labor])
        await db_session.commit()

        engine = KnowledgeEngine(db_session)
        results = await engine.search("规则", "租赁合同")  # 非劳动类型
        assert any("通用规则" in r for r in results)
        assert not any("劳动规则" in r for r in results)


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


class TestKnowledgeGetLaws:
    """法规检索测试"""

    async def test_get_laws_empty(self, db_session):
        """测试空数据库法规检索"""
        engine = KnowledgeEngine(db_session)
        laws = await engine.get_laws()
        assert laws == []

    async def test_get_laws_single_law(self, db_session):
        """测试单部法规检索"""
        ref1 = LegalReference(
            law_name="中华人民共和国民法典",
            article_number="第四百九十六条",
            content="格式条款是当事人为了重复使用而预先拟定...",
            tags=json.dumps(["格式条款", "公平原则"], ensure_ascii=False),
        )
        ref2 = LegalReference(
            law_name="中华人民共和国民法典",
            article_number="第四百九十七条",
            content="有下列情形之一的，该格式条款无效...",
            tags=json.dumps(["格式条款无效"], ensure_ascii=False),
        )
        db_session.add_all([ref1, ref2])
        await db_session.commit()

        engine = KnowledgeEngine(db_session)
        laws = await engine.get_laws()
        assert len(laws) == 1
        assert laws[0]["name"] == "中华人民共和国民法典"
        assert laws[0]["articles"] == 2
        assert "格式条款" in laws[0]["tags"]

    async def test_get_laws_multiple_laws(self, db_session):
        """测试多部法规检索"""
        ref1 = LegalReference(
            law_name="中华人民共和国民法典",
            article_number="第四百六十九条",
            content="当事人订立合同...",
            tags=json.dumps(["合同形式"], ensure_ascii=False),
        )
        ref2 = LegalReference(
            law_name="中华人民共和国劳动合同法",
            article_number="第十条",
            content="建立劳动关系，应当订立书面劳动合同...",
            tags=json.dumps(["书面合同"], ensure_ascii=False),
        )
        db_session.add_all([ref1, ref2])
        await db_session.commit()

        engine = KnowledgeEngine(db_session)
        laws = await engine.get_laws()
        assert len(laws) == 2
        names = {law["name"] for law in laws}
        assert "中华人民共和国民法典" in names
        assert "中华人民共和国劳动合同法" in names

    async def test_get_laws_tag_aggregation(self, db_session):
        """测试法规标签聚合"""
        ref1 = LegalReference(
            law_name="中华人民共和国民法典",
            article_number="第四百九十六条",
            content="格式条款...",
            tags=json.dumps(["格式条款", "公平原则"], ensure_ascii=False),
        )
        ref2 = LegalReference(
            law_name="中华人民共和国民法典",
            article_number="第四百九十七条",
            content="格式条款无效...",
            tags=json.dumps(["格式条款", "无效情形"], ensure_ascii=False),
        )
        db_session.add_all([ref1, ref2])
        await db_session.commit()

        engine = KnowledgeEngine(db_session)
        laws = await engine.get_laws()
        assert len(laws) == 1
        # 标签应该合并去重
        assert set(laws[0]["tags"]) == {"格式条款", "公平原则", "无效情形"}

    async def test_get_laws_invalid_json_tags(self, db_session):
        """测试法规标签 JSON 无效时的容错"""
        ref = LegalReference(
            law_name="测试法规",
            article_number="第一条",
            content="测试内容",
            tags="invalid json",  # 无效 JSON
        )
        db_session.add(ref)
        await db_session.commit()

        engine = KnowledgeEngine(db_session)
        laws = await engine.get_laws()
        assert len(laws) == 1
        assert laws[0]["tags"] == []  # 无效标签应返回空列表

    async def test_get_laws_null_tags(self, db_session):
        """测试法规标签为 None 时的容错"""
        ref = LegalReference(
            law_name="测试法规",
            article_number="第一条",
            content="测试内容",
            tags=None,
        )
        db_session.add(ref)
        await db_session.commit()

        engine = KnowledgeEngine(db_session)
        laws = await engine.get_laws()
        assert len(laws) == 1
        assert laws[0]["tags"] == []

    async def test_get_laws_sorted_by_name(self, db_session):
        """测试法规按名称排序"""
        ref1 = LegalReference(law_name="劳动合同法", article_number="第一条", content="内容1")
        ref2 = LegalReference(law_name="民法典", article_number="第一条", content="内容2")
        ref3 = LegalReference(law_name="广告法", article_number="第一条", content="内容3")
        db_session.add_all([ref1, ref2, ref3])
        await db_session.commit()

        engine = KnowledgeEngine(db_session)
        laws = await engine.get_laws()
        names = [law["name"] for law in laws]
        assert names == sorted(names)  # 应按名称排序


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


class TestTriggerAutoLearning:
    """自动学习管道测试"""

    async def test_auto_learning_creates_rule(self, db_session):
        """测试从反馈创建新规则"""
        # 创建完整的合同 -> 分析 -> 条款链
        contract = Contract(
            id="learn_contract",
            title="自动学习合同",
            type="租赁合同",
        )
        analysis = Analysis(
            id="learn_analysis",
            contract_id="learn_contract",
            model_used="deepseek-chat",
            overall_score=60,
            summary="风险较高",
            recommendation="negotiate_first",
        )
        clause = ClauseAnalysis(
            id="learn_clause",
            analysis_id="learn_analysis",
            clause_number="第一条",
            clause_content="本合同约定甲方应在签订后三日内支付全部租金",
            risk_level="yellow",
            risk_type="付款期限过短",
            risk_summary="付款期限偏短",
            plain_explanation="付款时间太紧",
        )
        db_session.add_all([contract, analysis, clause])
        await db_session.commit()

        engine = KnowledgeEngine(db_session)
        result = await engine.trigger_auto_learning(clause)

        # 应成功创建规则
        assert result is not None
        assert result["success"] is True
        assert result["id"] is not None

        # 验证规则内容
        stmt = select(KnowledgeRule).where(KnowledgeRule.id == result["id"])
        db_result = await db_session.execute(stmt)
        rule = db_result.scalar_one_or_none()
        assert rule is not None
        assert rule.rule_text == "本合同约定甲方应在签订后三日内支付全部租金"
        assert rule.source == "auto_learned"
        assert rule.confidence == 0.6
        # 类别应通过 Analysis -> Contract 映射为 "租赁"
        assert rule.category == "租赁"

    async def test_auto_learning_empty_content_skips(self, db_session):
        """测试空条款内容跳过学习"""
        clause = ClauseAnalysis(
            id="empty_clause",
            analysis_id="empty_analysis",
            clause_number="第一条",
            clause_content="",
            risk_level="green",
        )
        db_session.add(clause)
        await db_session.commit()

        engine = KnowledgeEngine(db_session)
        result = await engine.trigger_auto_learning(clause)
        assert result is None

    async def test_auto_learning_whitespace_content_skips(self, db_session):
        """测试纯空白条款内容跳过学习"""
        clause = ClauseAnalysis(
            id="ws_clause",
            analysis_id="ws_analysis",
            clause_number="第一条",
            clause_content="   \n\t  ",
            risk_level="green",
        )
        db_session.add(clause)
        await db_session.commit()

        engine = KnowledgeEngine(db_session)
        result = await engine.trigger_auto_learning(clause)
        assert result is None

    async def test_auto_learning_duplicate_skips(self, db_session):
        """测试重复规则跳过学习"""
        # 预先插入相同内容的规则
        existing_rule = KnowledgeRule(
            id="existing_rule",
            category="租赁",
            rule_text="已有规则内容",
            is_active=True,
        )
        db_session.add(existing_rule)
        await db_session.commit()

        clause = ClauseAnalysis(
            id="dup_clause",
            analysis_id="dup_analysis",
            clause_number="第一条",
            clause_content="已有规则内容",
            risk_level="red",
            risk_type="违约金过高",
        )
        db_session.add(clause)
        await db_session.commit()

        engine = KnowledgeEngine(db_session)
        result = await engine.trigger_auto_learning(clause)
        assert result is None  # 应跳过，因为规则已存在

    async def test_auto_learning_category_from_contract_type(self, db_session):
        """测试通过 Analysis -> Contract 正确映射规则类别"""
        # 创建劳动合同的完整链
        contract = Contract(
            id="labor_contract",
            title="劳动合同",
            type="劳动合同",
        )
        analysis = Analysis(
            id="labor_analysis",
            contract_id="labor_contract",
            model_used="deepseek-chat",
            overall_score=80,
        )
        clause = ClauseAnalysis(
            id="labor_clause",
            analysis_id="labor_analysis",
            clause_number="第一条",
            clause_content="试用期不得超过六个月",
            risk_level="yellow",
            risk_type="试用期过长",
        )
        db_session.add_all([contract, analysis, clause])
        await db_session.commit()

        engine = KnowledgeEngine(db_session)
        result = await engine.trigger_auto_learning(clause)

        assert result is not None
        stmt = select(KnowledgeRule).where(KnowledgeRule.id == result["id"])
        db_result = await db_session.execute(stmt)
        rule = db_result.scalar_one_or_none()
        # 类别应映射为 "劳动"
        assert rule.category == "劳动"

    async def test_auto_learning_no_analysis_fallback(self, db_session):
        """测试无 Analysis 关联时使用通用类别"""
        clause = ClauseAnalysis(
            id="orphan_clause",
            analysis_id="nonexistent_analysis",
            clause_number="第一条",
            clause_content="无关联分析的条款内容",
            risk_level="red",
        )
        db_session.add(clause)
        await db_session.commit()

        engine = KnowledgeEngine(db_session)
        result = await engine.trigger_auto_learning(clause)

        assert result is not None
        stmt = select(KnowledgeRule).where(KnowledgeRule.id == result["id"])
        db_result = await db_session.execute(stmt)
        rule = db_result.scalar_one_or_none()
        # 无关联分析时应使用默认 "通用" 类别
        assert rule.category == "通用"

    async def test_auto_learning_unknown_contract_type(self, db_session):
        """测试未知合同类型使用通用类别"""
        contract = Contract(
            id="unknown_type_contract",
            title="未知类型合同",
            type="特许经营合同",  # 不在 TYPE_CATEGORY_MAP 中
        )
        analysis = Analysis(
            id="unknown_analysis",
            contract_id="unknown_type_contract",
            model_used="deepseek-chat",
            overall_score=70,
        )
        clause = ClauseAnalysis(
            id="unknown_clause",
            analysis_id="unknown_analysis",
            clause_number="第一条",
            clause_content="特许经营费为五万元",
            risk_level="yellow",
            risk_type="费用过高",
        )
        db_session.add_all([contract, analysis, clause])
        await db_session.commit()

        engine = KnowledgeEngine(db_session)
        result = await engine.trigger_auto_learning(clause)

        assert result is not None
        stmt = select(KnowledgeRule).where(KnowledgeRule.id == result["id"])
        db_result = await db_session.execute(stmt)
        rule = db_result.scalar_one_or_none()
        # 未知类型应映射为 "通用"
        assert rule.category == "通用"
