"""Worker failure and evaluation semantics tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from server.core.llm import StructuredLLMResponse
from server.core.workers.parser import ClauseItem
from server.core.workers import workers as workers_module
from server.core.workers.workers import (
    ClauseRisk,
    analyze_dimension,
    analyze_dimension_with_context,
)


def _clause() -> ClauseItem:
    return ClauseItem(
        id="1",
        type="payment",
        title="付款",
        text="验收后付款",
        relevance=["financial"],
    )


def _risk(level: str, *, dimension: str = "general", status: str = "completed") -> ClauseRisk:
    return ClauseRisk(
        clause_id="1",
        risk_level=level,
        dimension=dimension,
        analysis_status=status,
    )


@pytest.mark.parametrize(
    ("levels", "should_resolve"),
    [
        (("red", "yellow"), False),
        (("yellow", "green"), False),
        (("red", "green"), True),
    ],
)
def test_detect_conflicts_keeps_all_valid_rating_disagreements(levels, should_resolve):
    conflicts = workers_module.detect_conflicts(
        [_risk(levels[0], dimension="equity"), _risk(levels[1], dimension="financial")]
    )

    assert set(conflicts) == {"1"}
    assert callable(getattr(workers_module, "requires_resolution", None))
    assert workers_module.requires_resolution(conflicts["1"]) is should_resolve


def test_detect_conflicts_ignores_unknown_and_failed_results():
    conflicts = workers_module.detect_conflicts(
        [
            _risk("red", dimension="equity"),
            _risk("unknown", dimension="financial", status="failed"),
            _risk("green", dimension="general", status="failed"),
        ]
    )

    assert conflicts == {}


def test_requires_resolution_ignores_failed_ratings_even_if_levels_are_red_and_green():
    assert workers_module.requires_resolution(
        [
            _risk("red", dimension="equity", status="failed"),
            _risk("green", dimension="financial", status="failed"),
        ]
    ) is False


@pytest.mark.asyncio
async def test_empty_worker_response_is_unknown_and_requires_review():
    llm = MagicMock()
    llm.chat_structured = AsyncMock()
    llm.chat_structured.return_value = StructuredLLMResponse(content="", parsed=None)

    results = await analyze_dimension("financial", [_clause()], llm, "服务合同")

    assert len(results) == 1
    risk = results[0]
    assert risk.risk_level == "unknown"
    assert risk.analysis_status == "failed"
    assert risk.review_required is True
    assert "financial" in risk.review_reason


@pytest.mark.asyncio
async def test_invalid_worker_json_is_unknown_and_requires_review():
    llm = MagicMock()
    llm.chat_structured = AsyncMock()
    llm.chat_structured.return_value = StructuredLLMResponse(
        content="not json", parsed=None
    )
    llm.parse_json = MagicMock(return_value=None)

    results = await analyze_dimension("financial", [_clause()], llm, "服务合同")

    assert len(results) == 1
    risk = results[0]
    assert risk.risk_level == "unknown"
    assert risk.analysis_status == "failed"
    assert risk.review_required is True
    assert "financial" in risk.review_reason


@pytest.mark.asyncio
async def test_structured_worker_response_missing_risk_level_requires_review():
    llm = MagicMock()
    llm.chat_structured = AsyncMock()
    llm.chat_structured.return_value = StructuredLLMResponse(
        content='{"risks":[{"clause_id":"1"}]}', parsed=None
    )
    llm.parse_json = MagicMock(return_value={"risks": [{"clause_id": "1"}]})

    results = await analyze_dimension("financial", [_clause()], llm, "服务合同")

    assert len(results) == 1
    risk = results[0]
    assert risk.risk_level == "unknown"
    assert risk.analysis_status == "failed"
    assert risk.review_required is True


@pytest.mark.asyncio
async def test_foreign_clause_id_is_failed_for_requested_clause():
    llm = MagicMock()
    llm.chat_structured = AsyncMock()
    llm.chat_structured.return_value = StructuredLLMResponse(
        content='{"risks":[{"clause_id":"999","risk_level":"green"}]}',
        parsed=None,
    )
    llm.parse_json = MagicMock(
        return_value={"risks": [{"clause_id": "999", "risk_level": "green"}]}
    )

    results = await analyze_dimension("financial", [_clause()], llm, "服务合同")

    assert len(results) == 1
    assert results[0].clause_id == "1"
    assert results[0].risk_level == "unknown"
    assert results[0].analysis_status == "failed"
    assert results[0].review_required is True


@pytest.mark.asyncio
async def test_second_pass_foreign_clause_id_is_failed_for_requested_clause():
    clause = _clause()
    llm = MagicMock()
    llm.chat_structured = AsyncMock()
    llm.chat_structured.return_value = StructuredLLMResponse(
        content='{"clause_id":"999","risk_level":"green"}',
        parsed=None,
    )
    llm.parse_json = MagicMock(
        return_value={"clause_id": "999", "risk_level": "green"}
    )

    result = await analyze_dimension_with_context(
        "financial", clause, llm, "服务合同", "- equity: yellow"
    )

    assert result is not None
    assert result.clause_id == "1"
    assert result.risk_level == "unknown"
    assert result.analysis_status == "failed"
    assert result.review_required is True


@pytest.mark.asyncio
async def test_worker_filters_citations_to_current_law_whitelist():
    llm = MagicMock()
    llm.chat_structured = AsyncMock(return_value=StructuredLLMResponse(
        content='{"risks":[{"clause_id":"1","risk_level":"yellow",'
        '"legal_basis":"自由文本依据","citation_ids":["law-1","forged-law"]}]}',
        parsed=None,
    ))
    llm.parse_json = MagicMock(return_value={
        "risks": [{
            "clause_id": "1",
            "risk_level": "yellow",
            "legal_basis": "自由文本依据",
            "citation_ids": ["law-1", "forged-law"],
        }]
    })

    results = await analyze_dimension(
        "financial",
        [_clause()],
        llm,
        "服务合同",
        kb_laws=[{"id": "law-1", "law_name": "民法典", "content": "违约金"}],
    )

    assert results[0].citation_ids == ["law-1"]
    assert results[0].legal_basis == "自由文本依据"
    assert results[0].review_required is True
    assert results[0].review_reason == "法条引用未通过校验"


@pytest.mark.asyncio
async def test_worker_does_not_treat_legal_basis_as_citation():
    llm = MagicMock()
    llm.chat_structured = AsyncMock(return_value=StructuredLLMResponse(
        content='{"risks":[{"clause_id":"1","risk_level":"green",'
        '"legal_basis":"《民法典》第五百八十五条"}]}',
        parsed=None,
    ))
    llm.parse_json = MagicMock(return_value={
        "risks": [{
            "clause_id": "1",
            "risk_level": "green",
            "legal_basis": "《民法典》第五百八十五条",
        }]
    })

    result = (await analyze_dimension(
        "financial", [_clause()], llm, "服务合同", kb_laws=[]
    ))[0]

    assert result.citation_ids == []
    assert result.legal_basis
    assert result.review_required is False
