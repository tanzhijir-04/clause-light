"""分析结束后触发 Distill 测试"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest

from server.core.agent import ContractAgent
from server.core.document_ingress import DocumentResult
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


def _parse() -> ParseResult:
    return ParseResult(
        contract_type="租赁合同",
        contract_type_en="rental",
        complexity="standard",
        recommended_model="fast",
        clauses=[
            ClauseItem(
                id="1",
                type="termination",
                title="期限",
                text="租期一年",
                relevance=["equity"],
            )
        ],
    )


@pytest.mark.asyncio
async def test_distill_called_once_on_success(db_session):
    """分析成功结束时 distill_from_analysis 被调用 1 次。"""
    distill_mock = AsyncMock(return_value={"atoms": 0, "rules": 0, "skills": 0, "wiki": 0})

    async def _fake_dimension(
        dim, clauses, llm, contract_type, kb_rules=None, kb_laws=None, memory_context=""
    ):
        if dim == "equity":
            return [ClauseRisk(clause_id="1", risk_level="green", issue="ok", severity=1)]
        return []

    @asynccontextmanager
    async def _factory():
        yield db_session

    agent = ContractAgent(llm=AsyncMock(), ocr=AsyncMock())

    with (
        patch(
            "server.core.agent.document_ingress.ingest",
            new_callable=AsyncMock,
            return_value=_make_doc("租赁合同"),
        ),
        patch("server.core.agent.parse_contract", new_callable=AsyncMock, return_value=_parse()),
        patch("server.core.agent.analyze_dimension", side_effect=_fake_dimension),
        patch(
            "server.core.agent.evaluate",
            new_callable=AsyncMock,
            return_value=EvaluationResult(
                overall_score=80,
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
        patch(
            "server.core.distill.pipeline.distill_from_analysis",
            distill_mock,
        ),
    ):
        result = await agent.analyze(file_path="test.pdf")

    assert result.error == ""
    assert result.session_id
    assert distill_mock.await_count == 1


@pytest.mark.asyncio
async def test_distill_error_does_not_set_result_error(db_session):
    """Distill 抛错不影响 result.error。"""

    async def _boom(*args, **kwargs):
        raise RuntimeError("distill crashed")

    async def _fake_dimension(
        dim, clauses, llm, contract_type, kb_rules=None, kb_laws=None, memory_context=""
    ):
        if dim == "equity":
            return [ClauseRisk(clause_id="1", risk_level="green", issue="ok", severity=1)]
        return []

    @asynccontextmanager
    async def _factory():
        yield db_session

    agent = ContractAgent(llm=AsyncMock(), ocr=AsyncMock())

    with (
        patch(
            "server.core.agent.document_ingress.ingest",
            new_callable=AsyncMock,
            return_value=_make_doc("租赁合同"),
        ),
        patch("server.core.agent.parse_contract", new_callable=AsyncMock, return_value=_parse()),
        patch("server.core.agent.analyze_dimension", side_effect=_fake_dimension),
        patch(
            "server.core.agent.evaluate",
            new_callable=AsyncMock,
            return_value=EvaluationResult(
                overall_score=80,
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
        patch(
            "server.core.distill.pipeline.distill_from_analysis",
            side_effect=_boom,
        ),
    ):
        result = await agent.analyze(file_path="test.pdf")

    assert result.error == ""
    assert result.overall_score == 80
