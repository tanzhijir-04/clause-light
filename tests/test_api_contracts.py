"""合同 API 接口测试"""

from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from server.models.database import Analysis, ClauseAnalysis, Contract


class TestListContracts:
    """合同列表接口测试"""

    async def test_list_empty(self, client):
        """测试空列表"""
        response = await client.get("/api/contracts/")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_with_contracts(self, client, db_session):
        """测试有数据的列表"""
        contract = Contract(
            id="list_contract_1",
            title="测试合同",
            type="租赁合同",
        )
        db_session.add(contract)
        await db_session.commit()

        response = await client.get("/api/contracts/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "测试合同"
        assert data[0]["type"] == "租赁合同"

    async def test_list_with_search(self, client, db_session):
        """测试搜索筛选"""
        contracts = [
            Contract(id=f"search_{i}", title=f"合同 {i}", type="租赁合同")
            for i in range(5)
        ]
        db_session.add_all(contracts)
        await db_session.commit()

        response = await client.get("/api/contracts/?search=合同 2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "合同 2"

    async def test_list_with_type_filter(self, client, db_session):
        """测试类型筛选"""
        contracts = [
            Contract(id="type_1", title="租赁合同", type="租赁合同"),
            Contract(id="type_2", title="劳动合同", type="劳动合同"),
        ]
        db_session.add_all(contracts)
        await db_session.commit()

        response = await client.get("/api/contracts/?type=rental")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["typeEn"] == "rental"


class TestGetContract:
    """合同详情接口测试"""

    async def test_get_existing(self, client, db_session):
        """测试获取存在的合同"""
        contract = Contract(
            id="detail_contract",
            title="详情合同",
            type="租赁合同",
        )
        db_session.add(contract)
        await db_session.commit()

        response = await client.get("/api/contracts/detail_contract")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "详情合同"
        assert data["status"] == "pending"

    async def test_get_nonexistent(self, client):
        """测试获取不存在的合同"""
        response = await client.get("/api/contracts/nonexistent")
        assert response.status_code == 404
        assert "合同不存在" in response.json()["detail"]

    async def test_get_with_analysis(self, client, db_session):
        """测试获取有分析结果的合同"""
        contract = Contract(
            id="analyzed_contract",
            title="已分析合同",
            type="劳动合同",
        )
        analysis = Analysis(
            id="analysis_1",
            contract_id="analyzed_contract",
            model_used="deepseek-chat",
            overall_score=85,
            summary="风险可控",
            recommendation="sign",
        )
        clause = ClauseAnalysis(
            id="clause_1",
            analysis_id="analysis_1",
            clause_number="第一条",
            clause_title="合同目的",
            clause_content="本合同旨在...",
            risk_level="red",
            risk_type="违约金过高",
            risk_summary="违约金过高",
            plain_explanation="违约金过高",
            legal_basis="《合同法》",
            severity_score=8,
        )
        db_session.add_all([contract, analysis, clause])
        await db_session.commit()

        response = await client.get("/api/contracts/analyzed_contract")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "analyzed"
        assert data["score"] == 85
        assert data["redCount"] == 1
        assert len(data["clauses"]) == 1


class TestAnalyzeContract:
    """合同分析接口测试"""

    async def test_analyze_no_file(self, client):
        """测试无文件上传"""
        response = await client.post("/api/contracts/analyze")
        assert response.status_code == 422  # Unprocessable Entity

    async def test_analyze_unsupported_format(self, client):
        """测试不支持的文件格式"""
        response = await client.post(
            "/api/contracts/analyze",
            files={"file": ("test.txt", b"content", "text/plain")},
        )
        assert response.status_code == 400
        assert "不支持的文件格式" in response.json()["detail"]

    async def test_analyze_with_mock_agent(self, client, db_session):
        """测试使用 mock Agent 分析"""
        # Mock Agent 返回结果
        mock_result = MagicMock()
        mock_result.contract_id = "mock_contract_id"
        mock_result.contract_type = "租赁合同"
        mock_result.overall_score = 75
        mock_result.recommendation = "negotiate_first"
        mock_result.model_used = "deepseek-chat"
        mock_result.summary = "合同风险中等"
        mock_result.red_count = 1
        mock_result.yellow_count = 2
        mock_result.green_count = 5
        mock_result.clauses = [
            {
                "clause_number": "第一条",
                "title": "合同目的",
                "content": "本合同旨在...",
                "risk_level": "green",
                "risk_type": "无风险",
                "risk_summary": "正常条款",
                "plain_explanation": "正常",
                "legal_basis": "《合同法》",
                "severity_score": 1,
                "suggested_clause": "",
                "can_negotiate": False,
            }
        ]

        mock_result.ocr_text = "合同原文内容"
        mock_result.error = ""
        with patch("server.api.contracts.ContractAgent") as MockAgent:
            MockAgent.return_value.analyze = AsyncMock(return_value=mock_result)

            response = await client.post(
                "/api/contracts/analyze",
                files={"file": ("test.pdf", b"fake pdf content", "application/pdf")},
                data={"contract_type": "租赁合同"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["score"] == 75


class TestSubmitFeedback:
    """提交反馈接口测试"""

    async def test_submit_feedback_success(self, client, db_session):
        """测试成功提交反馈"""
        clause = ClauseAnalysis(
            id="feedback_clause",
            analysis_id="feedback_analysis",
            clause_number="第一条",
            clause_content="测试条款",
            risk_level="red",
        )
        db_session.add(clause)
        await db_session.commit()

        response = await client.post(
            "/api/contracts/test_contract/feedback",
            data={
                "clause_analysis_id": "feedback_clause",
                "feedback": "correct",
            },
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

        # 验证反馈已保存
        stmt = select(ClauseAnalysis).where(ClauseAnalysis.id == "feedback_clause")
        result = await db_session.execute(stmt)
        updated = result.scalar_one_or_none()
        assert updated.user_feedback == "correct"

    async def test_submit_feedback_nonexistent_clause(self, client):
        """测试不存在的条款"""
        response = await client.post(
            "/api/contracts/test_contract/feedback",
            data={
                "clause_analysis_id": "nonexistent",
                "feedback": "correct",
            },
        )
        assert response.status_code == 404
