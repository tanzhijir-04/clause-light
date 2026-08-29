"""合同 API 接口测试"""

from __future__ import annotations

import json
from io import BytesIO
from typing import AsyncGenerator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from server.models.database import Analysis, ClauseAnalysis, Contract, WorkerRiskResult, get_db


@pytest_asyncio.fixture
async def contracts_client() -> AsyncGenerator[AsyncClient, None]:
    """仅挂载 contracts 路由，避免 server.main 依赖 qrcode 等可选包"""
    from fastapi import FastAPI
    from server.api.contracts import router
    from tests.conftest import override_get_db

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


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

    async def test_analyze_no_file(self, contracts_client):
        """测试无文件上传"""
        response = await contracts_client.post("/api/contracts/analyze")
        assert response.status_code == 422  # Unprocessable Entity

    async def test_analyze_unsupported_format(self, contracts_client):
        """测试不支持的文件格式"""
        response = await contracts_client.post(
            "/api/contracts/analyze",
            files={"file": ("test.txt", b"content", "text/plain")},
        )
        assert response.status_code == 400
        assert "不支持的文件格式" in response.json()["detail"]

    async def test_remote_analysis_requires_consent_before_persisting_upload(self, contracts_client, db_session, tmp_path):
        from server.core.llm import LLMProcessingPlan

        with patch(
            "server.api.contracts.get_llm_gateway",
            return_value=SimpleNamespace(
                get_processing_plan=lambda task: LLMProcessingPlan(
                    "deepseek", "deepseek-chat", "remote"
                )
            ),
        ):
            response = await contracts_client.post(
                "/api/contracts/analyze",
                files={"file": ("private.pdf", b"private contract", "application/pdf")},
            )
        assert response.status_code == 400
        assert "远程模型服务" in response.json()["detail"]
        assert (await db_session.execute(
            select(Contract).where(Contract.title == "private")
        )).scalars().all() == []

    async def test_analyze_docx_accepted(self, contracts_client, db_session):
        """测试 .docx 不再因格式被拒（mock Agent）"""
        mock_result = MagicMock()
        mock_result.contract_id = "docx_contract_id"
        mock_result.contract_type = "租赁合同"
        mock_result.overall_score = 80
        mock_result.recommendation = "sign"
        mock_result.model_used = "deepseek-chat"
        mock_result.summary = "风险可控"
        mock_result.red_count = 0
        mock_result.yellow_count = 0
        mock_result.green_count = 3
        mock_result.clauses = []
        mock_result.ocr_text = "# 合同\n条款"
        mock_result.error = ""

        from tests.conftest import test_session_factory

        with (
            patch("server.api.contracts.ContractAgent") as MockAgent,
            patch(
                "server.api.contracts.async_session_factory",
                test_session_factory,
            ),
        ):
            MockAgent.return_value.analyze = AsyncMock(return_value=mock_result)

            response = await contracts_client.post(
                "/api/contracts/analyze",
                files={
                    "file": (
                        "lease.docx",
                        b"PK\x03\x04fake-docx",
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
                data={"contract_type": "租赁合同", "allow_remote_processing": "true"},
            )
            # 关键：扩展名白名单放行，不再 400「不支持的文件格式」
            assert response.status_code == 200
            assert "不支持的文件格式" not in response.text
            MockAgent.return_value.analyze.assert_called_once()
            call = MockAgent.return_value.analyze.call_args
            file_path = call.kwargs.get("file_path") or (
                call.args[0] if call.args else ""
            )
            assert str(file_path).endswith(".docx")

    async def test_analyze_with_mock_agent(self, contracts_client, db_session):
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

        from tests.conftest import test_session_factory

        with (
            patch("server.api.contracts.ContractAgent") as MockAgent,
            patch(
                "server.api.contracts.async_session_factory",
                test_session_factory,
            ),
        ):
            MockAgent.return_value.analyze = AsyncMock(return_value=mock_result)

            response = await contracts_client.post(
                "/api/contracts/analyze",
                files={"file": ("test.pdf", b"fake pdf content", "application/pdf")},
                data={"contract_type": "租赁合同", "allow_remote_processing": "true"},
            )
            assert response.status_code == 200
            # SSE 流：至少推送了 result 事件
            assert "result" in response.text or '"score"' in response.text
            MockAgent.return_value.analyze.assert_called_once()


class TestPersistAnalysisResult:
    """分析结果持久化：保存必须在后台任务内完成，断开连接也不丢结果"""

    async def test_persist_saves_analysis_and_clauses(self, db_session):
        """持久化成功时写入分析记录与条款分析，并更新合同信息"""
        from server.api.contracts import persist_analysis_result
        from tests.conftest import test_session_factory

        contract = Contract(id="persist_contract", title="待分析", type="其他")
        db_session.add(contract)
        await db_session.commit()

        result = SimpleNamespace(
            ocr_text="合同全文",
            contract_type="租赁合同",
            contract_id="persist_analysis",
            model_used="deepseek-chat",
            overall_score=55,
            summary="存在风险",
            recommendation="negotiate_first",
            clauses=[
                {
                    "clause_number": "第一条",
                    "title": "租金",
                    "content": "逾期每日 5‰ 违约金",
                    "risk_level": "red",
                    "risk_type": "违约金过高",
                    "risk_summary": "违约金过高",
                    "plain_explanation": "比例偏高",
                    "legal_basis": "《民法典》",
                    "severity_score": 8,
                    "suggested_clause": "建议调整",
                    "can_negotiate": True,
                    "analysis_status": "completed",
                    "needs_review": False,
                    "review_reason": "",
                    "source_start": 0,
                    "source_end": 13,
                    "citation_ids": ["law-1"],
                }
            ],
            analysis_status="completed",
            review_reasons={},
            processing_mode="remote",
            worker_risks=[{
                "clause_id": "第一条",
                "dimension": "financial",
                "phase": "initial",
                "risk_level": "red",
                "risk_type": "违约金过高",
                "issue": "比例偏高",
                "unfavorable_to": "乙方",
                "severity": 8,
                "suggestion": "建议调整",
                "legal_basis": "",
                "citation_ids": ["law-1"],
                "analysis_status": "completed",
                "failure_reason": "",
                "review_required": False,
                "review_reason": "",
            }],
            session_id="mem_session_1",
            error="",
        )

        err = await persist_analysis_result("persist_contract", result, test_session_factory)

        assert err is None

        analysis = await db_session.get(Analysis, "persist_analysis")
        assert analysis is not None
        assert analysis.contract_id == "persist_contract"
        assert analysis.overall_score == 55
        assert analysis.recommendation == "negotiate_first"
        assert analysis.processing_mode == "remote"
        assert analysis.source == "remote"
        assert "mem_session_1" in (analysis.raw_result or "")

        clauses = (
            await db_session.execute(
                select(ClauseAnalysis).where(ClauseAnalysis.analysis_id == "persist_analysis")
            )
        ).scalars().all()
        assert len(clauses) == 1
        assert clauses[0].risk_level == "red"
        assert clauses[0].severity_score == 8
        worker_rows = (
            await db_session.execute(
                select(WorkerRiskResult).where(WorkerRiskResult.analysis_id == "persist_analysis")
            )
        ).scalars().all()
        assert len(worker_rows) == 1
        assert worker_rows[0].phase == "initial"
        assert worker_rows[0].citation_ids == '["law-1"]'

        refreshed = await db_session.get(Contract, "persist_contract")
        await db_session.refresh(refreshed)
        assert refreshed.type == "租赁合同"
        assert refreshed.ocr_text == "合同全文"

    async def test_persist_skips_when_result_has_no_contract_id(self, db_session):
        """结果缺少 contract_id 时只更新合同信息，不写分析记录"""
        from server.api.contracts import persist_analysis_result
        from tests.conftest import test_session_factory

        contract = Contract(id="persist_no_analysis", title="待分析", type="其他")
        db_session.add(contract)
        await db_session.commit()

        result = SimpleNamespace(
            ocr_text="全文",
            contract_type="租赁合同",
            contract_id="",
            clauses=[],
            error="",
        )

        err = await persist_analysis_result("persist_no_analysis", result, test_session_factory)
        assert err is None

        analyses = (
            await db_session.execute(
                select(Analysis).where(Analysis.contract_id == "persist_no_analysis")
            )
        ).scalars().all()
        assert analyses == []


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

    async def test_submit_feedback_incorrect_triggers_auto_learning(self, client, db_session):
        """测试 incorrect 反馈触发自动学习"""
        # 创建合同、分析、条款
        contract = Contract(
            id="auto_learn_contract",
            title="自动学习测试合同",
            type="租赁合同",
        )
        analysis = Analysis(
            id="auto_learn_analysis",
            contract_id="auto_learn_contract",
            model_used="deepseek-chat",
            overall_score=60,
            summary="风险较高",
            recommendation="negotiate_first",
        )
        clause = ClauseAnalysis(
            id="auto_learn_clause",
            analysis_id="auto_learn_analysis",
            clause_number="第一条",
            clause_content="本合同约定甲方应在签订后三日内支付全部租金",
            risk_level="yellow",
            risk_type="付款期限过短",
            risk_summary="付款期限偏短",
            plain_explanation="付款时间太紧",
            legal_basis="《合同法》",
            severity_score=5,
        )
        db_session.add_all([contract, analysis, clause])
        await db_session.commit()

        response = await client.post(
            "/api/contracts/auto_learn_contract/feedback",
            data={
                "clause_analysis_id": "auto_learn_clause",
                "feedback": "incorrect",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["autoLearned"] is True

        # 验证条款反馈已保存
        stmt = select(ClauseAnalysis).where(ClauseAnalysis.id == "auto_learn_clause")
        result = await db_session.execute(stmt)
        updated = result.scalar_one_or_none()
        assert updated.user_feedback == "incorrect"

        # 验证新规则已创建
        from server.models.database import KnowledgeRule

        rule_stmt = select(KnowledgeRule).where(KnowledgeRule.source == "auto_learned")
        rule_result = await db_session.execute(rule_stmt)
        rules = rule_result.scalars().all()
        assert len(rules) >= 1
        # 规则类别应通过 Analysis -> Contract 映射为 "租赁"
        assert rules[0].category == "租赁"
        assert rules[0].confidence == 0.6


class TestDeleteContract:
    """合同删除接口测试"""

    async def test_delete_existing_contract(self, client, db_session):
        """测试删除存在的合同"""
        contract = Contract(
            id="delete_test",
            title="待删除合同",
            type="租赁合同",
        )
        db_session.add(contract)
        await db_session.commit()

        response = await client.delete("/api/contracts/delete_test")
        assert response.status_code == 200
        assert response.json()["success"] is True

        # 验证合同已删除
        stmt = select(Contract).where(Contract.id == "delete_test")
        result = await db_session.execute(stmt)
        assert result.scalar_one_or_none() is None

    async def test_delete_nonexistent_contract(self, client):
        """测试删除不存在的合同"""
        response = await client.delete("/api/contracts/nonexistent")
        assert response.status_code == 404
        assert "合同不存在" in response.json()["detail"]

    async def test_delete_cascade_analysis_and_clauses(self, client, db_session):
        """测试级联删除分析记录和条款分析"""
        contract = Contract(
            id="cascade_contract",
            title="级联删除测试",
            type="劳动合同",
        )
        analysis = Analysis(
            id="cascade_analysis",
            contract_id="cascade_contract",
            model_used="deepseek-chat",
            overall_score=70,
            summary="测试",
            recommendation="sign",
        )
        clause1 = ClauseAnalysis(
            id="cascade_clause_1",
            analysis_id="cascade_analysis",
            clause_number="第一条",
            clause_content="条款一内容",
            risk_level="red",
            risk_type="违约金过高",
        )
        clause2 = ClauseAnalysis(
            id="cascade_clause_2",
            analysis_id="cascade_analysis",
            clause_number="第二条",
            clause_content="条款二内容",
            risk_level="green",
        )
        worker = WorkerRiskResult(
            id="cascade_worker",
            analysis_id="cascade_analysis",
            clause_number="第一条",
            dimension="financial",
            phase="initial",
            risk_level="unknown",
            analysis_status="failed",
        )
        db_session.add_all([contract, analysis, clause1, clause2, worker])
        await db_session.commit()

        response = await client.delete("/api/contracts/cascade_contract")
        assert response.status_code == 200

        # 验证分析记录已删除
        analysis_stmt = select(Analysis).where(Analysis.contract_id == "cascade_contract")
        analysis_result = await db_session.execute(analysis_stmt)
        assert analysis_result.scalars().all() == []

        # 验证条款分析已删除
        clause_stmt = select(ClauseAnalysis).where(ClauseAnalysis.analysis_id == "cascade_analysis")
        clause_result = await db_session.execute(clause_stmt)
        assert clause_result.scalars().all() == []

        worker_stmt = select(WorkerRiskResult).where(WorkerRiskResult.analysis_id == "cascade_analysis")
        worker_result = await db_session.execute(worker_stmt)
        assert worker_result.scalars().all() == []

    async def test_delete_source_file_cleanup(self, client, db_session, tmp_path):
        """测试删除时清理源文件"""
        # 创建临时源文件
        source_file = tmp_path / "test_source.pdf"
        source_file.write_bytes(b"fake pdf content")

        contract = Contract(
            id="file_cleanup_contract",
            title="文件清理测试",
            type="租赁合同",
            source_file=str(source_file),
        )
        db_session.add(contract)
        await db_session.commit()

        response = await client.delete("/api/contracts/file_cleanup_contract")
        assert response.status_code == 200

        # 验证源文件已删除
        assert not source_file.exists()

    async def test_delete_missing_source_file_no_error(self, client, db_session):
        """测试源文件不存在时删除不报错"""
        contract = Contract(
            id="no_file_contract",
            title="无源文件测试",
            type="租赁合同",
            source_file="/nonexistent/path/file.pdf",
        )
        db_session.add(contract)
        await db_session.commit()

        # 不应报错
        response = await client.delete("/api/contracts/no_file_contract")
        assert response.status_code == 200
        assert response.json()["success"] is True
