"""知识库 API 接口测试"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from server.models.database import KnowledgeRule


class TestListRules:
    """规则列表接口测试"""

    async def test_list_empty(self, client):
        """测试空列表"""
        response = await client.get("/api/knowledge/rules")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_with_rules(self, client, db_session):
        """测试有数据的列表"""
        rules = [
            KnowledgeRule(
                id=f"api_rule_{i}",
                category="租赁",
                rule_text=f"规则 {i}",
                confidence=0.5 + i * 0.1,
                is_active=True,
            )
            for i in range(3)
        ]
        db_session.add_all(rules)
        await db_session.commit()

        response = await client.get("/api/knowledge/rules")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    async def test_list_with_search(self, client, db_session):
        """测试搜索筛选"""
        rules = [
            KnowledgeRule(
                id=f"search_rule_{i}",
                category="租赁",
                rule_text=f"租赁合同规则 {i}",
                is_active=True,
            )
            for i in range(5)
        ]
        db_session.add_all(rules)
        await db_session.commit()

        response = await client.get("/api/knowledge/rules?search=规则 2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    async def test_list_with_category_filter(self, client, db_session):
        """测试类别筛选"""
        rules = [
            KnowledgeRule(
                id="cat_rule_1",
                category="租赁",
                rule_text="租赁规则",
                is_active=True,
            ),
            KnowledgeRule(
                id="cat_rule_2",
                category="劳动",
                rule_text="劳动规则",
                is_active=True,
            ),
        ]
        db_session.add_all(rules)
        await db_session.commit()

        response = await client.get("/api/knowledge/rules?category=租赁")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["category"] == "租赁"


class TestCreateRule:
    """新增规则接口测试"""

    async def test_create_rule_success(self, client):
        """测试成功新增规则"""
        response = await client.post(
            "/api/knowledge/rules",
            json={
                "rule_text": "测试规则",
                "category": "租赁",
                "trigger_keywords": ["测试"],
                "confidence": 0.7,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["id"] is not None

    async def test_create_rule_default_values(self, client):
        """测试新增规则默认值"""
        response = await client.post(
            "/api/knowledge/rules",
            json={"rule_text": "默认值规则"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestUpdateRule:
    """更新规则接口测试"""

    async def test_update_rule_success(self, client, db_session):
        """测试成功更新规则"""
        rule = KnowledgeRule(
            id="update_api_rule",
            category="租赁",
            rule_text="原始规则",
            confidence=0.5,
        )
        db_session.add(rule)
        await db_session.commit()

        response = await client.put(
            "/api/knowledge/rules/update_api_rule",
            json={
                "rule_text": "更新后的规则",
                "confidence": 0.9,
            },
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

    async def test_update_nonexistent_rule(self, client):
        """测试更新不存在的规则"""
        response = await client.put(
            "/api/knowledge/rules/nonexistent",
            json={"rule_text": "测试"},
        )
        # 应该返回 200（静默成功）
        assert response.status_code == 200


class TestDeleteRule:
    """删除规则接口测试"""

    async def test_delete_rule_success(self, client, db_session):
        """测试成功删除规则"""
        rule = KnowledgeRule(
            id="delete_api_rule",
            category="租赁",
            rule_text="待删除规则",
        )
        db_session.add(rule)
        await db_session.commit()

        response = await client.delete("/api/knowledge/rules/delete_api_rule")
        assert response.status_code == 200
        assert response.json()["success"] is True

    async def test_delete_nonexistent_rule(self, client):
        """测试删除不存在的规则"""
        response = await client.delete("/api/knowledge/rules/nonexistent")
        assert response.status_code == 200


class TestKnowledgeStats:
    """知识库统计接口测试"""

    async def test_get_stats(self, client):
        """测试获取统计"""
        response = await client.get("/api/knowledge/stats")
        assert response.status_code == 200
        data = response.json()
        assert "totalRules" in data
        assert "avgConfidence" in data


class TestPendingRules:
    """待审核规则接口测试"""

    async def test_get_pending(self, client):
        """测试获取待审核规则"""
        response = await client.get("/api/knowledge/pending")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_approve_rule(self, client, db_session):
        """测试通过规则"""
        rule = KnowledgeRule(
            id="approve_api_rule",
            category="租赁",
            rule_text="待通过规则",
            confidence=0.5,
            source="auto_learned",
        )
        db_session.add(rule)
        await db_session.commit()

        response = await client.post("/api/knowledge/pending/approve_api_rule/approve")
        assert response.status_code == 200
        assert response.json()["success"] is True

    async def test_reject_rule(self, client, db_session):
        """测试拒绝规则"""
        rule = KnowledgeRule(
            id="reject_api_rule",
            category="租赁",
            rule_text="待拒绝规则",
            confidence=0.4,
            source="auto_learned",
        )
        db_session.add(rule)
        await db_session.commit()

        response = await client.post("/api/knowledge/pending/reject_api_rule/reject")
        assert response.status_code == 200
        assert response.json()["success"] is True


class TestGetLaws:
    """法规列表接口测试"""

    async def test_get_laws_empty(self, client):
        """测试空法规列表"""
        response = await client.get("/api/knowledge/laws")
        assert response.status_code == 200
        assert response.json() == []
