"""Task 3: Stage 1 traceability and degradation tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.core.agent import ContractAgent
from server.core.document_ingress import DocumentResult
from server.core.llm import StructuredLLMResponse
from server.core.schemas.llm_outputs import ParseClauseSchema, ParseResultSchema
from server.core.workers.evaluator import EvaluationResult
from server.core.workers.parser import (
    TYPE_TO_WORKERS,
    ClauseItem,
    normalize_contract_text,
    parse_contract,
)
from server.core.workers.workers import ClauseRisk


def _structured_result(*clauses: ParseClauseSchema) -> StructuredLLMResponse:
    return StructuredLLMResponse(
        parsed=ParseResultSchema(
            contract_type="租赁合同",
            clauses=list(clauses),
        )
    )


def _configure_session(mock_factory: MagicMock) -> None:
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    execute_result = MagicMock()
    execute_result.scalars.return_value.all.return_value = []
    execute_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=execute_result)
    session.flush = AsyncMock()
    session.get = AsyncMock(return_value=None)
    session.commit = AsyncMock()
    mock_factory.return_value = session


def test_normalize_contract_text_matches_frontend_spacing_semantics() -> None:
    text = "  第一条\n  付款   条件\n\n\n第二段  "

    assert normalize_contract_text(text) == "第一条 付款 条件\n\n第二段"


@pytest.mark.asyncio
async def test_repeated_clause_text_uses_monotonic_source_cursor() -> None:
    full_text = "前言 付款条款。中间 付款条款。"
    llm = MagicMock()
    llm.chat_structured = AsyncMock(
        return_value=_structured_result(
            ParseClauseSchema(id="1", type="payment", title="付款一", text="付款条款"),
            ParseClauseSchema(id="2", type="payment", title="付款二", text="付款条款"),
        )
    )

    result = await parse_contract(full_text, llm)

    first = full_text.index("付款条款")
    second = full_text.index("付款条款", first + 1)
    assert [(c.source_start, c.source_end) for c in result.clauses] == [
        (first, first + len("付款条款")),
        (second, second + len("付款条款")),
    ]
    assert result.clauses[0].source_start != result.clauses[1].source_start


@pytest.mark.asyncio
async def test_clause_location_uses_normalized_text_coordinates() -> None:
    original = "标题\n  付款   条件\n第二段"
    normalized = normalize_contract_text(original)
    llm = MagicMock()
    llm.chat_structured = AsyncMock(
        return_value=_structured_result(
            ParseClauseSchema(id="1", type="payment", title="付款", text="付款\n 条件"),
        )
    )

    result = await parse_contract(original, llm)

    start = normalized.index("付款 条件")
    assert result.clauses[0].text == "付款 条件"
    assert result.clauses[0].source_start == start
    assert result.clauses[0].source_end == start + len("付款 条件")


@pytest.mark.asyncio
async def test_rewritten_clause_without_match_requires_review_and_has_no_range() -> None:
    llm = MagicMock()
    llm.chat_structured = AsyncMock(
        return_value=_structured_result(
            ParseClauseSchema(
                id="1",
                type="payment",
                title="付款",
                text="完全改写且原文没有任何对应内容的条款",
            ),
        )
    )

    result = await parse_contract("第一条 付款条件，乙方应及时付款。", llm)

    clause = result.clauses[0]
    assert (clause.source_start, clause.source_end) == (-1, -1)
    assert clause.review_required is True
    assert clause.review_reason == "条款原文定位失败"
    assert result.review_required is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response_setup, expected_reason",
    [
        ("empty", "LLM 返回空内容"),
        ("exception", "LLM 调用失败: LLM 不可用"),
    ],
)
async def test_parse_failure_returns_complete_normalized_full_text_fallback(
    response_setup: str, expected_reason: str
) -> None:
    full_text = "合同正文\n" + ("付款条款。" * 500)
    llm = MagicMock()
    if response_setup == "empty":
        llm.chat_structured = AsyncMock(
            return_value=StructuredLLMResponse(content="", parsed=None)
        )
    else:
        llm.chat_structured = AsyncMock(side_effect=RuntimeError("LLM 不可用"))

    result = await parse_contract(full_text, llm)

    normalized = normalize_contract_text(full_text)
    assert result.parse_status == "fallback"
    assert result.review_required is True
    assert result.fallback_reason == expected_reason
    assert result.failure_reason == expected_reason
    assert result.clauses[0].text == normalized
    assert len(result.clauses[0].text) > 2000
    assert (result.clauses[0].source_start, result.clauses[0].source_end) == (
        0,
        len(normalized),
    )


@pytest.mark.asyncio
async def test_invalid_relevance_uses_clause_mapping_and_marks_review() -> None:
    llm = MagicMock()
    llm.chat_structured = AsyncMock(
        return_value=StructuredLLMResponse(content='{"clauses": []}', parsed=None)
    )
    llm.parse_json = MagicMock(
        return_value={
            "contract_type": "租赁合同",
            "complexity": "standard",
            "recommended_model": "fast",
            "clauses": [
                {
                    "id": "1",
                    "type": "payment",
                    "title": "付款",
                    "text": "验收后付款",
                    "relevance": ["unknown-worker"],
                }
            ],
        }
    )

    result = await parse_contract("验收后付款", llm)

    clause = result.clauses[0]
    assert clause.relevance == TYPE_TO_WORKERS["payment"]
    assert clause.review_required is True
    assert clause.review_reason


@pytest.mark.asyncio
async def test_invalid_relevance_is_sanitized_before_worker_dispatch() -> None:
    full_text = "验收后付款"
    parse_result = MagicMock()
    parse_result.contract_type = "租赁合同"
    parse_result.contract_type_en = "rental"
    parse_result.recommended_model = "fast"
    parse_result.parse_failed = False
    parse_result.failure_reason = ""
    parse_result.review_required = True
    parse_result.fallback_reason = ""
    parse_result.clauses = [
        ClauseItem(
            id="1",
            type="payment",
            title="付款",
            text=full_text,
            relevance=["unknown-worker"],  # type: ignore[list-item]
            review_required=True,
            review_reason="relevance 无效，已按条款类型映射",
        )
    ]

    captured: dict[str, list[str]] = {}

    async def fake_dimension(
        dimension: str,
        clauses: list[ClauseItem],
        llm: MagicMock,
        contract_type: str,
        kb_rules: list[str] | None = None,
        kb_laws: list[dict] | None = None,
        memory_context: str = "",
    ) -> list[ClauseRisk]:
        if clauses:
            captured[dimension] = list(clauses[0].relevance)
        if dimension == "financial":
            return [ClauseRisk(clause_id="1", risk_level="green", severity=1)]
        return []

    with (
        patch("server.core.agent.document_ingress.ingest", new_callable=AsyncMock) as ingest,
        patch("server.core.agent.parse_contract", new_callable=AsyncMock) as parse,
        patch("server.core.agent.analyze_dimension", side_effect=fake_dimension),
        patch("server.core.agent.evaluate", new_callable=AsyncMock) as evaluate,
        patch("server.core.agent.async_session_factory") as session_factory,
        patch.object(ContractAgent, "_trigger_distill", new=AsyncMock()),
    ):
        ingest.return_value = DocumentResult(
            full_text=full_text,
            markdown=full_text,
            source="test",
            confidence_avg=1.0,
        )
        parse.return_value = parse_result
        evaluate.return_value = EvaluationResult(
            overall_score=90,
            risk_distribution={"red": 0, "yellow": 0, "green": 1, "unknown": 0},
            recommendation="sign",
            one_line_summary="可签署",
        )
        _configure_session(session_factory)
        result = await ContractAgent(llm=MagicMock()).analyze("test.txt")

    assert captured["financial"] == TYPE_TO_WORKERS["payment"]
    assert all("unknown-worker" not in relevance for relevance in captured.values())
    assert result.needs_review == ["1"]
    assert "relevance 无效，已按条款类型映射" in result.review_reasons["1"]
    assert result.clauses[0]["needs_review"] is True
