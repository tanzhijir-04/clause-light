"""ContractAgent 记忆装配集成测试"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest

from server.core.agent import AnalysisResult, ContractAgent, TYPE_EN_MAP
from server.core.document_ingress import DocumentResult
from server.core.memory import store
from server.core.workers.evaluator import EvaluationResult
from server.core.workers.parser import ClauseItem, ParseResult
from server.core.workers.workers import ClauseRisk


def _make_doc(text: str) -> DocumentResult:
    return DocumentResult(
        full_text=text,
        markdown=text,
        source="paddle",
        confidence_avg=0.95,
    )


@pytest.mark.asyncio
async def test_analyze_sets_session_id_and_injects_atom(db_session):
    """有原子记忆时：session_id 非空，且 Worker messages 含原子内容。"""
    await store.upsert_atom(
        db_session,
        {
            "content": "用户是乙方视角，适用于租赁合同",
            "status": "active",
            "confidence": 0.9,
            "contract_type": "租赁合同",
        },
    )
    await db_session.commit()

    captured: list = []

    class FakeLLM:
        def parse_json(self, content: str):
            try:
                return json.loads(content)
            except Exception:
                return []

        async def chat(self, messages, task="analysis", **kwargs):
            captured.append(messages)

            class R:
                content = (
                    '[{"clause_id":"1","risk_level":"green","risk_type":"ok",'
                    '"issue":"本维度无明显风险","unfavorable_to":"","severity":1,'
                    '"suggestion":"","legal_basis":""}]'
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
    @asynccontextmanager
    async def _factory():
        yield db_session

    parse_result = ParseResult(
        contract_type="租赁合同",
        contract_type_en="rental",
        complexity="standard",
        recommended_model="fast",
        clauses=[
            ClauseItem(
                id="1",
                type="termination",
                title="租赁期限",
                text="租赁期限为一年",
                relevance=["equity"],
            )
        ],
    )
    eval_result = EvaluationResult(
        overall_score=80,
        risk_distribution={"red": 0, "yellow": 0, "green": 1},
        recommendation="sign",
        one_line_summary="可控",
        top_risks=[],
    )

    agent = ContractAgent(llm=FakeLLM(), ocr=AsyncMock())

    with (
        patch(
            "server.core.agent.document_ingress.ingest",
            new_callable=AsyncMock,
            return_value=_make_doc("租赁合同 甲方 乙方"),
        ),
        patch("server.core.agent.parse_contract", new_callable=AsyncMock, return_value=parse_result),
        patch("server.core.agent.evaluate", new_callable=AsyncMock, return_value=eval_result),
        patch("server.core.agent.async_session_factory", _factory),
        patch(
            "server.core.knowledge.KnowledgeEngine.search",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "server.core.knowledge.KnowledgeEngine.search_laws",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        result = await agent.analyze(file_path="test.pdf")

    assert isinstance(result, AnalysisResult)
    assert result.error == ""
    assert result.session_id
    blob = json.dumps(captured, ensure_ascii=False)
    assert "乙方" in blob


@pytest.mark.asyncio
async def test_analyze_without_memory_still_ok(db_session):
    """无记忆时仍返回正常 AnalysisResult，不报错。"""

    class FakeLLM:
        def parse_json(self, content: str):
            return []

        async def chat(self, messages, task="analysis", **kwargs):
            class R:
                content = "[]"

            return R()

        async def chat_structured(self, messages, schema, task="analysis", **kwargs):
            from server.core.llm import StructuredLLMResponse

            r = await self.chat(messages, task=task)
            return StructuredLLMResponse(content=r.content, parsed=None, via="fallback")

    @asynccontextmanager
    async def _factory():
        yield db_session

    parse_result = ParseResult(
        contract_type="其他",
        contract_type_en="other",
        complexity="standard",
        recommended_model="fast",
        clauses=[
            ClauseItem(
                id="1",
                type="other",
                title="全文",
                text="简单合同",
                relevance=["general"],
            )
        ],
    )

    agent = ContractAgent(llm=FakeLLM(), ocr=AsyncMock())

    with (
        patch(
            "server.core.agent.document_ingress.ingest",
            new_callable=AsyncMock,
            return_value=_make_doc("简单合同"),
        ),
        patch("server.core.agent.parse_contract", new_callable=AsyncMock, return_value=parse_result),
        patch(
            "server.core.agent.evaluate",
            new_callable=AsyncMock,
            return_value=EvaluationResult(
                overall_score=70,
                risk_distribution={"red": 0, "yellow": 0, "green": 1},
                recommendation="sign",
                one_line_summary="ok",
            ),
        ),
        patch("server.core.agent.async_session_factory", _factory),
        patch(
            "server.core.knowledge.KnowledgeEngine.search",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "server.core.knowledge.KnowledgeEngine.search_laws",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        result = await agent.analyze(file_path="test.pdf")

    assert result.error == ""
    assert result.session_id
    assert result.overall_score == 70
