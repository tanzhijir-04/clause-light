"""Agent Harness 测试 — 三段式 Pipeline"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.core.agent import AnalysisResult, ContractAgent, TYPE_EN_MAP
from server.core.document_ingress import DocumentResult
from server.core.workers.parser import ClauseItem, ParseResult
from server.core.workers.workers import ClauseRisk
from server.core.workers.evaluator import EvaluationResult


class TestAnalysisResult:
    """分析结果数据类测试"""

    def test_default_values(self):
        """测试默认值"""
        result = AnalysisResult()
        assert result.contract_id == ""
        assert result.overall_score == 0
        assert result.clauses == []
        assert result.red_count == 0

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
        assert result.contract_id == ""
        assert "为空" in result.error

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
        async def _fake_dimension(dim, clauses, llm, contract_type, kb_rules=None, kb_laws=None):
            if dim == "equity":
                return [ClauseRisk(clause_id="1", risk_level="green", issue="正常条款", severity=1)]
            elif dim == "dispute":
                return [ClauseRisk(clause_id="1", risk_level="green", issue="正常条款", severity=1)]
            return []

        mock_dimension.side_effect = _fake_dimension

        # Stage 3: evaluate
        mock_evaluate.return_value = _mock_eval_result()

        # 知识库 mock
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_factory.return_value = mock_session

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

        async def _fake_dimension(dim, clauses, llm, contract_type, kb_rules=None, kb_laws=None):
            if dim == "general":
                return [ClauseRisk(clause_id="1", risk_level="yellow", risk_type="试用期过长", issue="试用期超过法定上限", severity=6, suggestion="缩短试用期", legal_basis="《劳动合同法》")]
            return []

        mock_dimension.side_effect = _fake_dimension
        mock_evaluate.return_value = _mock_eval_result(score=60, yellow=1, green=0, recommendation="negotiate_first", summary="试用期条款需修改")

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_factory.return_value = mock_session

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

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_factory.return_value = mock_session

        result = await self.agent.analyze(file_path="test.pdf")
        # Stage 1 失败时兜底：全文作为一个条款
        assert len(result.clauses) > 0, "LLM 失败时条款不应丢失"
        assert result.clauses[0]["risk_level"] == "green"

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
        assert result.contract_id == ""
        assert "文档解析失败" in result.error

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

        async def _fake_dimension(dim, clauses, llm, contract_type, kb_rules=None, kb_laws=None):
            if dim == "equity":
                return [ClauseRisk(clause_id="1", risk_level="red", risk_type="违约金过高", issue="年化超24%", severity=9, suggestion="降低比例", legal_basis="《合同法》")]
            elif dim == "financial":
                return [ClauseRisk(clause_id="1", risk_level="red", risk_type="违约金过高", issue="财务风险", severity=8)]
            elif dim == "general":
                return [ClauseRisk(clause_id="2", risk_level="green", issue="正常条款", severity=1)]
            return []

        mock_dimension.side_effect = _fake_dimension
        mock_evaluate.return_value = _mock_eval_result(score=35, red=1, green=1, recommendation="negotiate_first", summary="有高风险条款")

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_factory.return_value = mock_session

        result = await self.agent.analyze(file_path="test.pdf")
        assert result.overall_score == 35
        assert result.red_count == 1
        assert result.green_count == 1
        # 红色条款应有修改建议（来自 Worker 的 suggestion）
        red_clause = [c for c in result.clauses if c.get("risk_level") == "red"]
        assert len(red_clause) == 1

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
        async def _fake_dimension(dim, clauses, llm, contract_type, kb_rules=None, kb_laws=None):
            if dim == "equity":
                raise Exception("Worker 崩溃")
            return []

        mock_dimension.side_effect = _fake_dimension
        mock_evaluate.return_value = _mock_eval_result(score=50, green=1)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_factory.return_value = mock_session

        result = await self.agent.analyze(file_path="test.pdf")
        # equity Worker 失败，但其他 Worker 和整体流程应继续
        assert len(result.clauses) >= 1
        assert result.contract_type == "租赁合同"

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

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_factory.return_value = mock_session

        result = await self.agent.analyze(file_path="contract.docx")
        assert "条款一" in result.ocr_text
        mock_ingest.assert_called()
        # _retry 经 lambda 调用 ingest(file_path)
        assert any(
            "contract.docx" in str(c)
            for c in mock_ingest.call_args_list
        )
