"""Agent Harness 测试 — 三段式 Pipeline"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.core.agent import AnalysisResult, ContractAgent, TYPE_EN_MAP
from server.core.document_ingress import DocumentResult
from server.core.llm import StructuredLLMResponse
from server.core.workers.parser import ClauseItem, ParseResult
from server.core.workers.workers import ClauseRisk
from server.core.workers.evaluator import EvaluationResult, evaluate as real_evaluate


class TestAnalysisResult:
    """分析结果数据类测试"""

    def test_default_values(self):
        """测试默认值"""
        result = AnalysisResult()
        assert result.contract_id == ""
        assert result.overall_score is None
        assert result.clauses == []
        assert result.red_count == 0
        assert result.analysis_status == "failed"
        assert result.recommendation == "manual_review"

    def test_custom_values(self):
        """测试自定义值"""
        result = AnalysisResult(
            contract_id="test_id",
            contract_type="租赁合同",
            overall_score=85,
            clauses=[{"clause_number": "第一条"}],
            red_count=1,
            yellow_count=2,
            green_count=5,
        )
        assert result.contract_id == "test_id"
        assert len(result.clauses) == 1


class TestTypeEnMap:
    """类型映射测试"""

    def test_known_types(self):
        """测试已知类型映射"""
        assert TYPE_EN_MAP["租赁合同"] == "rental"
        assert TYPE_EN_MAP["劳动合同"] == "labor"
        assert TYPE_EN_MAP["装修合同"] == "renovation"
        assert TYPE_EN_MAP["外包合同"] == "outsourcing"

    def test_unknown_type(self):
        """测试未知类型"""
        assert TYPE_EN_MAP.get("未知类型", "other") == "other"


def _make_doc_result(text: str, confidence: float = 0.95, source: str = "paddle") -> DocumentResult:
    """创建 DocumentIngress 结果"""
    return DocumentResult(
        full_text=text,
        markdown=text,
        source=source,
        confidence_avg=confidence,
    )


def _mock_parse_result(contract_type="租赁合同", clauses=None):
    """创建 Stage 1 解析结果"""
    if clauses is None:
        clauses = [ClauseItem(id="1", type="termination", title="租赁期限", text="租赁期限为一年", relevance=["equity", "dispute"])]
    return ParseResult(
        contract_type=contract_type,
        contract_type_en=TYPE_EN_MAP.get(contract_type, "other"),
        complexity="standard",
        recommended_model="fast",
        clauses=clauses,
    )


def _mock_eval_result(score=85, red=0, yellow=0, green=1, recommendation="sign", summary="合同风险可控"):
    """创建 Stage 3 评估结果"""
    return EvaluationResult(
        overall_score=score,
        risk_distribution={"red": red, "yellow": yellow, "green": green},
        recommendation=recommendation,
        one_line_summary=summary,
        top_risks=[],
    )


def _configure_session(mock_factory):
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    execute_result = MagicMock()
    execute_result.scalars.return_value.all.return_value = []
    execute_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=execute_result)
    mock_session.flush = AsyncMock()
    mock_session.get = AsyncMock(return_value=None)
    mock_session.commit = AsyncMock()
    mock_factory.return_value = mock_session


class TestContractAgent:
    """合同分析 Agent 测试 — 三段式 Pipeline"""

    def setup_method(self):
        """初始化 Mock 对象"""
        self.mock_llm = MagicMock()
        self.mock_ocr = MagicMock()
        self.agent = ContractAgent(llm=self.mock_llm, ocr=self.mock_ocr)

    @patch("server.core.agent.document_ingress.ingest", new_callable=AsyncMock)
    async def test_analyze_empty_ocr(self, mock_ingest):
        """测试文档解析返回空结果"""
        mock_ingest.return_value = _make_doc_result("")

        result = await self.agent.analyze(file_path="test.pdf")
        assert result.contract_id
        assert "为空" in result.error
        assert result.analysis_status == "failed"
        assert result.recommendation == "manual_review"
        assert result.review_reasons["pipeline"]

    @patch("server.core.agent.evaluate")
    @patch("server.core.agent.analyze_dimension")
    @patch("server.core.agent.parse_contract")
    @patch("server.core.agent.async_session_factory")
    @patch("server.core.agent.document_ingress.ingest", new_callable=AsyncMock)
    async def test_analyze_with_text(
        self, mock_ingest, mock_factory, mock_parse, mock_dimension, mock_evaluate
    ):
        """测试正常分析流程"""
        mock_ingest.return_value = _make_doc_result(
            "租赁合同\n甲方：张三\n乙方：李四\n第一条 租赁期限"
        )

        # Stage 1: parse_contract
        mock_parse.return_value = _mock_parse_result()

        # Stage 2: analyze_dimension (5 个维度并行)
        async def _fake_dimension(
            dim, clauses, llm, contract_type, kb_rules=None, kb_laws=None, memory_context=""
        ):
            if dim == "equity":
                return [ClauseRisk(clause_id="1", risk_level="green", issue="正常条款", severity=1)]
            elif dim == "dispute":
                return [ClauseRisk(clause_id="1", risk_level="green", issue="正常条款", severity=1)]
            return []

        mock_dimension.side_effect = _fake_dimension

        # Stage 3: evaluate
        mock_evaluate.return_value = _mock_eval_result()

        # 知识库 / 记忆 mock（装配失败应降级，不阻断主流程）
        _configure_session(mock_factory)

        result = await self.agent.analyze(file_path="test.pdf")
        assert result.overall_score == 85
        assert result.contract_type == "租赁合同"
        assert len(result.clauses) >= 1
        assert "租赁合同" in result.ocr_text
        mock_parse.assert_called_once()
        mock_ingest.assert_called()

    @patch("server.core.agent.evaluate")
    @patch("server.core.agent.analyze_dimension")
    @patch("server.core.agent.parse_contract")
    @patch("server.core.agent.async_session_factory")
    @patch("server.core.agent.document_ingress.ingest", new_callable=AsyncMock)
    async def test_analyze_with_hint(
        self, mock_ingest, mock_factory, mock_parse, mock_dimension, mock_evaluate
    ):
        """测试带类型提示"""
        mock_ingest.return_value = _make_doc_result("劳动合同内容...")

        clauses = [ClauseItem(id="1", type="other", title="试用期", text="试用期三个月", relevance=["general"])]
        mock_parse.return_value = _mock_parse_result(contract_type="劳动合同", clauses=clauses)

        async def _fake_dimension(
            dim, clauses, llm, contract_type, kb_rules=None, kb_laws=None, memory_context=""
        ):
            if dim == "general":
                return [ClauseRisk(clause_id="1", risk_level="yellow", risk_type="试用期过长", issue="试用期超过法定上限", severity=6, suggestion="缩短试用期", legal_basis="《劳动合同法》")]
            return []

        mock_dimension.side_effect = _fake_dimension
        mock_evaluate.return_value = _mock_eval_result(score=60, yellow=1, green=0, recommendation="negotiate_first", summary="试用期条款需修改")

        _configure_session(mock_factory)

        result = await self.agent.analyze(
            file_path="test.pdf",
            contract_type_hint="劳动合同",
        )
        assert result.contract_type == "劳动合同"
        assert result.overall_score == 60

    @patch("server.core.agent.evaluate")
    @patch("server.core.agent.analyze_dimension")
    @patch("server.core.agent.parse_contract")
    @patch("server.core.agent.async_session_factory")
    @patch("server.core.agent.document_ingress.ingest", new_callable=AsyncMock)
    async def test_analyze_llm_failure_fallback(
        self, mock_ingest, mock_factory, mock_parse, mock_dimension, mock_evaluate
    ):
        """测试 LLM 完全失败时的兜底行为"""
        mock_ingest.return_value = _make_doc_result("合同内容")

        # Stage 1 失败
        mock_parse.side_effect = Exception("LLM 不可用")

        _configure_session(mock_factory)

        result = await self.agent.analyze(file_path="test.pdf")
        # Stage 1 失败时兜底：全文作为一个条款
        assert len(result.clauses) > 0, "LLM 失败时条款不应丢失"
        assert result.clauses[0]["risk_level"] == "unknown"
        assert result.clauses[0]["needs_review"] is True
        assert result.analysis_status == "failed"
        assert result.recommendation == "manual_review"

    @patch("server.core.agent.document_ingress.ingest", new_callable=AsyncMock)
    async def test_analyze_step_callback(self, mock_ingest):
        """测试步骤回调"""
        mock_ingest.return_value = _make_doc_result("")

        callback = AsyncMock()
        result = await self.agent.analyze(file_path="test.pdf", on_step=callback)

        callback.assert_called_once()

    @patch("server.core.agent.document_ingress.ingest", new_callable=AsyncMock)
    async def test_analyze_ocr_exception(self, mock_ingest):
        """测试文档解析异常处理"""
        mock_ingest.side_effect = Exception("解析崩溃")

        result = await self.agent.analyze(file_path="test.pdf")
        assert result.contract_id
        assert "文档解析失败" in result.error
        assert result.analysis_status == "failed"
        assert result.recommendation == "manual_review"
        assert result.review_reasons["pipeline"]

    @pytest.mark.asyncio
    async def test_evaluator_rejects_malformed_fallback_fields(self):
        valid = ClauseRisk(clause_id="1", risk_level="green", severity=1)
        failed = ClauseRisk(
            clause_id="2",
            risk_level="unknown",
            analysis_status="failed",
            review_required=True,
        )
        llm = MagicMock()
        malformed_payloads = [
            {
                "overall_score": "99",
                "recommendation": "sign",
                "risk_distribution": {"red": 0, "yellow": 0, "green": 1, "unknown": 0},
            },
            {
                "overall_score": 99,
                "recommendation": "invalid",
                "risk_distribution": {"red": 0, "yellow": 0, "green": 1, "unknown": 0},
            },
            {
                "overall_score": 99,
                "recommendation": "sign",
                "risk_distribution": {
                    "red": 0,
                    "yellow": 0,
                    "green": 1,
                    "unknown": 0,
                    "purple": 10,
                },
            },
        ]

        for malformed in malformed_payloads:
            llm.chat_structured = AsyncMock(
                return_value=StructuredLLMResponse(
                    content="malformed evaluation",
                    parsed=None,
                )
            )
            llm.parse_json = MagicMock(return_value=malformed)

            result = await real_evaluate([valid, failed], llm)

            assert result.overall_score is None
            assert result.recommendation == "manual_review"
            assert set(result.risk_distribution) == {"red", "yellow", "green", "unknown"}
            assert result.risk_distribution == {"red": 0, "yellow": 0, "green": 1, "unknown": 1}
            assert all(
                type(count) is int and count >= 0
                for count in result.risk_distribution.values()
            )
            assert result.needs_review == ["2"]

    @pytest.mark.asyncio
    async def test_evaluator_parse_json_failure_returns_safe_manual_review(self):
        valid = ClauseRisk(clause_id="1", risk_level="green", severity=1)
        failed = ClauseRisk(
            clause_id="2",
            risk_level="unknown",
            analysis_status="failed",
            review_required=True,
        )
        llm = MagicMock()
        llm.chat_structured = AsyncMock(
            return_value=StructuredLLMResponse(
                content="not json",
                parsed=None,
            )
        )
        llm.parse_json = MagicMock(side_effect=ValueError("malformed JSON"))

        result = await real_evaluate([valid, failed], llm)

        assert result.overall_score is None
        assert result.recommendation == "manual_review"
        assert result.risk_distribution == {
            "red": 0,
            "yellow": 0,
            "green": 1,
            "unknown": 1,
        }
        assert result.needs_review == ["2"]

    @pytest.mark.asyncio
    async def test_evaluator_keeps_review_for_conflicts_failures_and_invalid_citations(self):
        risks = [
            ClauseRisk(clause_id="1", risk_level="red", dimension="equity"),
            ClauseRisk(clause_id="1", risk_level="yellow", dimension="financial"),
            ClauseRisk(
                clause_id="2",
                risk_level="green",
                dimension="general",
                review_required=True,
                review_reason="法条引用未通过校验",
            ),
            ClauseRisk(
                clause_id="3",
                risk_level="unknown",
                analysis_status="failed",
                review_required=True,
            ),
        ]
        llm = MagicMock()
        llm.chat_structured = AsyncMock(
            return_value=StructuredLLMResponse(
                content='{"overall_score":60,"recommendation":"negotiate_first",'
                '"risk_distribution":{"red":1,"yellow":1,"green":1,"unknown":1}}',
                parsed=None,
            )
        )
        llm.parse_json = MagicMock(
            return_value={
                "overall_score": 60,
                "recommendation": "negotiate_first",
                "risk_distribution": {"red": 1, "yellow": 1, "green": 1, "unknown": 1},
            }
        )

        result = await real_evaluate(risks, llm)

        assert result.needs_review == ["1", "2", "3"]

    @patch("server.core.agent.evaluate")
    @patch("server.core.agent.analyze_dimension")
    @patch("server.core.agent.parse_contract")
    @patch("server.core.agent.async_session_factory")
    @patch("server.core.agent.document_ingress.ingest", new_callable=AsyncMock)
    async def test_analyze_risk_distribution(
        self, mock_ingest, mock_factory, mock_parse, mock_dimension, mock_evaluate
    ):
        """测试风险分布统计"""
        mock_ingest.return_value = _make_doc_result("合同内容")

        clauses = [
            ClauseItem(id="1", type="penalty", title="违约金", text="违约金50%", relevance=["equity", "financial"]),
            ClauseItem(id="2", type="force_majeure", title="不可抗力", text="不可抗力免责", relevance=["general"]),
        ]
        mock_parse.return_value = _mock_parse_result(clauses=clauses)

        async def _fake_dimension(
            dim, clauses, llm, contract_type, kb_rules=None, kb_laws=None, memory_context=""
        ):
            if dim == "equity":
                return [ClauseRisk(clause_id="1", risk_level="red", risk_type="违约金过高", issue="年化超24%", severity=9, suggestion="降低比例", legal_basis="《合同法》")]
            elif dim == "financial":
                return [ClauseRisk(clause_id="1", risk_level="red", risk_type="违约金过高", issue="财务风险", severity=8)]
            elif dim == "general":
                return [ClauseRisk(clause_id="2", risk_level="green", issue="正常条款", severity=1)]
            return []

        mock_dimension.side_effect = _fake_dimension
        mock_evaluate.return_value = _mock_eval_result(score=35, red=1, green=1, recommendation="negotiate_first", summary="有高风险条款")

        _configure_session(mock_factory)

        result = await self.agent.analyze(file_path="test.pdf")
        assert result.overall_score == 35
        assert result.red_count == 1
        assert result.green_count == 1
        # 红色条款应有修改建议（来自 Worker 的 suggestion）
        red_clause = [c for c in result.clauses if c.get("risk_level") == "red"]
        assert len(red_clause) == 1

    @patch("server.core.agent.analyze_dimension_with_context")
    @patch("server.core.agent.evaluate")
    @patch("server.core.agent.analyze_dimension")
    @patch("server.core.agent.parse_contract")
    @patch("server.core.agent.async_session_factory")
    @patch("server.core.agent.document_ingress.ingest", new_callable=AsyncMock)
    async def test_conflict_resolution_preserves_initial_history_and_uses_best_dimension(
        self,
        mock_ingest,
        mock_factory,
        mock_parse,
        mock_dimension,
        mock_evaluate,
        mock_resolve,
    ):
        mock_ingest.return_value = _make_doc_result("合同内容")
        clause = ClauseItem(
            id="1",
            type="payment",
            title="付款",
            text="验收后付款",
            relevance=["financial", "equity"],
        )
        mock_parse.return_value = _mock_parse_result(clauses=[clause])

        async def _fake_dimension(
            dim, clauses, llm, contract_type, kb_rules=None, kb_laws=None, memory_context=""
        ):
            if dim == "financial":
                return [
                    ClauseRisk(
                        clause_id="1",
                        risk_level="red",
                        dimension="financial",
                        severity=9,
                    )
                ]
            if dim == "equity":
                return [
                    ClauseRisk(
                        clause_id="1",
                        risk_level="green",
                        dimension="equity",
                        severity=1,
                    )
                ]
            return []

        mock_dimension.side_effect = _fake_dimension
        mock_resolve.return_value = ClauseRisk(
            clause_id="1",
            risk_level="yellow",
            dimension="financial",
            severity=2,
        )
        mock_evaluate.return_value = _mock_eval_result(
            score=60,
            red=0,
            yellow=1,
            green=0,
            recommendation="negotiate_first",
            summary="冲突已复核",
        )
        _configure_session(mock_factory)

        result = await self.agent.analyze(file_path="test.pdf")

        assert mock_resolve.call_args.args[0] == "financial"
        assert len(result.worker_risks) == 3
        assert {risk["phase"] for risk in result.worker_risks} == {"initial", "resolution"}
        assert sum(risk["phase"] == "resolution" for risk in result.worker_risks) == 1
        resolution = next(risk for risk in result.worker_risks if risk["phase"] == "resolution")
        assert resolution["analysis_status"] == "resolved"
        assert result.clauses[0]["risk_level"] == "yellow"
        assert result.clauses[0]["needs_review"] is True
        assert result.review_reasons["1"]

    @patch("server.core.agent.evaluate")
    @patch("server.core.agent.analyze_dimension")
    @patch("server.core.agent.parse_contract")
    @patch("server.core.agent.async_session_factory")
    @patch("server.core.agent.document_ingress.ingest", new_callable=AsyncMock)
    async def test_analyze_worker_failure_graceful(
        self, mock_ingest, mock_factory, mock_parse, mock_dimension, mock_evaluate
    ):
        """测试单个 Worker 失败时的优雅降级"""
        mock_ingest.return_value = _make_doc_result("合同内容")

        clauses = [ClauseItem(id="1", type="penalty", title="违约金", text="违约金50%", relevance=["equity", "financial"])]
        mock_parse.return_value = _mock_parse_result(clauses=clauses)

        # equity Worker 失败，其他正常
        async def _fake_dimension(
            dim, clauses, llm, contract_type, kb_rules=None, kb_laws=None, memory_context=""
        ):
            if dim == "equity":
                raise Exception("Worker 崩溃")
            if dim == "financial":
                return [ClauseRisk(clause_id="1", risk_level="green", severity=2)]
            return []

        mock_dimension.side_effect = _fake_dimension
        mock_evaluate.return_value = _mock_eval_result(score=50, green=1)

        _configure_session(mock_factory)

        result = await self.agent.analyze(file_path="test.pdf")
        # equity Worker 失败，但其他 Worker 和整体流程应继续
        assert len(result.clauses) >= 1
        assert result.contract_type == "租赁合同"
        assert result.analysis_status == "partial"
        assert result.needs_review == ["1"]

    @patch("server.core.agent.evaluate")
    @patch("server.core.agent.analyze_dimension")
    @patch("server.core.agent.parse_contract")
    @patch("server.core.agent.async_session_factory")
    @patch("server.core.agent.document_ingress.ingest", new_callable=AsyncMock)
    async def test_parse_failure_with_usable_worker_result_is_partial(
        self, mock_ingest, mock_factory, mock_parse, mock_dimension, mock_evaluate
    ):
        mock_ingest.return_value = _make_doc_result("合同内容")
        mock_parse.side_effect = RuntimeError("解析失败")

        async def _fake_dimension(
            dim, clauses, llm, contract_type, kb_rules=None, kb_laws=None, memory_context=""
        ):
            if dim == "general":
                return [ClauseRisk(clause_id="1", risk_level="green", severity=2)]
            return []

        mock_dimension.side_effect = _fake_dimension
        mock_evaluate.return_value = _mock_eval_result()
        _configure_session(mock_factory)

        result = await self.agent.analyze(file_path="test.pdf")

        assert result.analysis_status == "partial"
        assert result.error
        assert result.review_reasons["pipeline"]

    @patch("server.core.agent.evaluate")
    @patch("server.core.agent.analyze_dimension")
    @patch("server.core.agent.parse_contract")
    @patch("server.core.agent.async_session_factory")
    @patch("server.core.agent.document_ingress.ingest", new_callable=AsyncMock)
    async def test_parse_review_required_with_usable_worker_result_is_partial(
        self, mock_ingest, mock_factory, mock_parse, mock_dimension, mock_evaluate
    ):
        mock_ingest.return_value = _make_doc_result("合同内容")
        parse_result = _mock_parse_result(
            clauses=[
                ClauseItem(
                    id="1",
                    type="payment",
                    title="付款",
                    text="验收后付款",
                    relevance=["financial"],
                )
            ]
        )
        parse_result.review_required = True
        parse_result.fallback_reason = "解析结果需要人工确认"
        mock_parse.return_value = parse_result

        async def _fake_dimension(
            dim, clauses, llm, contract_type, kb_rules=None, kb_laws=None, memory_context=""
        ):
            if dim == "financial":
                return [ClauseRisk(clause_id="1", risk_level="green", severity=1)]
            return []

        mock_dimension.side_effect = _fake_dimension
        mock_evaluate.return_value = _mock_eval_result()
        _configure_session(mock_factory)

        result = await self.agent.analyze(file_path="test.pdf")

        assert result.analysis_status == "partial"
        assert result.analysis_status != "completed"
        assert "解析结果需要人工确认" in result.review_reasons["pipeline"]

    @patch("server.core.agent.analyze_dimension_with_context")
    @patch("server.core.agent.evaluate")
    @patch("server.core.agent.analyze_dimension")
    @patch("server.core.agent.parse_contract")
    @patch("server.core.agent.async_session_factory")
    @patch("server.core.agent.document_ingress.ingest", new_callable=AsyncMock)
    async def test_related_worker_exception_cannot_produce_unreviewed_green_clause(
        self,
        mock_ingest,
        mock_factory,
        mock_parse,
        mock_dimension,
        mock_evaluate,
        mock_resolve,
    ):
        mock_ingest.return_value = _make_doc_result("合同内容")
        clause = ClauseItem(
            id="1",
            type="payment",
            title="付款",
            text="验收后付款",
            relevance=["financial"],
        )
        mock_parse.return_value = _mock_parse_result(clauses=[clause])

        async def _fake_dimension(
            dim, clauses, llm, contract_type, kb_rules=None, kb_laws=None, memory_context=""
        ):
            if dim == "financial":
                raise RuntimeError("Worker 崩溃")
            return []

        mock_dimension.side_effect = _fake_dimension
        mock_evaluate.side_effect = real_evaluate
        _configure_session(mock_factory)

        result = await self.agent.analyze(file_path="test.pdf")

        assert result.clauses[0]["risk_level"] == "unknown"
        assert result.clauses[0]["needs_review"] is True
        assert result.green_count == 0

    @patch("server.core.agent.analyze_dimension_with_context")
    @patch("server.core.agent.evaluate")
    @patch("server.core.agent.analyze_dimension")
    @patch("server.core.agent.parse_contract")
    @patch("server.core.agent.async_session_factory")
    @patch("server.core.agent.document_ingress.ingest", new_callable=AsyncMock)
    async def test_foreign_resolution_id_is_not_scored_as_green(
        self,
        mock_ingest,
        mock_factory,
        mock_parse,
        mock_dimension,
        mock_evaluate,
        mock_resolve,
    ):
        mock_ingest.return_value = _make_doc_result("合同内容")
        clause = ClauseItem(
            id="1",
            type="payment",
            title="付款",
            text="验收后付款",
            relevance=["equity", "financial"],
        )
        mock_parse.return_value = _mock_parse_result(clauses=[clause])

        async def _fake_dimension(
            dim, clauses, llm, contract_type, kb_rules=None, kb_laws=None, memory_context=""
        ):
            if dim == "equity":
                return [ClauseRisk(clause_id="1", risk_level="red")]
            if dim == "financial":
                return [ClauseRisk(clause_id="1", risk_level="green")]
            return []

        mock_dimension.side_effect = _fake_dimension
        mock_resolve.return_value = ClauseRisk(
            clause_id="999", risk_level="green", severity=10
        )
        scored_risks = []

        async def _capture_evaluate(risks, llm):
            scored_risks.extend(risks)
            if any(
                risk.analysis_status in {"completed", "resolved"}
                and risk.risk_level == "green"
                for risk in risks
            ):
                return _mock_eval_result(score=80, green=1)
            return _mock_eval_result(
                score=None,
                green=0,
                recommendation="manual_review",
                summary="系统未形成可用评级，请人工复核",
            )

        mock_evaluate.side_effect = _capture_evaluate
        _configure_session(mock_factory)

        result = await self.agent.analyze(file_path="test.pdf")

        assert scored_risks
        assert all(risk.clause_id == "1" for risk in scored_risks)
        assert all(risk["clause_id"] != "999" for risk in result.worker_risks)
        assert result.clauses[0]["risk_level"] == "red"
        assert result.green_count == 0
        assert result.analysis_status == "partial"
        assert result.needs_review == ["1"]

    @patch("server.core.agent.analyze_dimension_with_context")
    @patch("server.core.agent.evaluate")
    @patch("server.core.agent.analyze_dimension")
    @patch("server.core.agent.parse_contract")
    @patch("server.core.agent.async_session_factory")
    @patch("server.core.agent.document_ingress.ingest", new_callable=AsyncMock)
    async def test_all_related_workers_failed_return_manual_review_unknown_clause(
        self,
        mock_ingest,
        mock_factory,
        mock_parse,
        mock_dimension,
        mock_evaluate,
        mock_resolve,
    ):
        mock_ingest.return_value = _make_doc_result("合同内容")
        clause = ClauseItem(
            id="1",
            type="payment",
            title="付款",
            text="验收后付款",
            relevance=["financial"],
        )
        mock_parse.return_value = _mock_parse_result(clauses=[clause])

        async def _fake_dimension(
            dim, clauses, llm, contract_type, kb_rules=None, kb_laws=None, memory_context=""
        ):
            if dim == "financial":
                raise RuntimeError("Worker 崩溃")
            return []

        mock_dimension.side_effect = _fake_dimension
        mock_evaluate.side_effect = real_evaluate
        _configure_session(mock_factory)

        result = await self.agent.analyze(file_path="test.pdf")

        assert result.clauses[0]["risk_level"] == "unknown"
        assert result.overall_score is None
        assert result.recommendation == "manual_review"
        assert result.green_count == 0
        assert result.needs_review == ["1"]
    @patch("server.core.agent.evaluate")
    @patch("server.core.agent.analyze_dimension")
    @patch("server.core.agent.parse_contract")
    @patch("server.core.agent.async_session_factory")
    @patch("server.core.agent.document_ingress.ingest", new_callable=AsyncMock)
    async def test_analyze_docx_via_ingest(
        self, mock_ingest, mock_factory, mock_parse, mock_dimension, mock_evaluate
    ):
        """测试 .docx 走 document_ingress（mock），ocr_text 仍填充"""
        mock_ingest.return_value = _make_doc_result(
            "# 租赁合同\n条款一", confidence=1.0, source="anydoc"
        )
        mock_parse.return_value = _mock_parse_result()
        mock_dimension.return_value = []
        mock_evaluate.return_value = _mock_eval_result()

        _configure_session(mock_factory)

        result = await self.agent.analyze(file_path="contract.docx")
        assert "条款一" in result.ocr_text
        mock_ingest.assert_called()
        # _retry 经 lambda 调用 ingest(file_path)
        assert any(
            "contract.docx" in str(c)
            for c in mock_ingest.call_args_list
        )
