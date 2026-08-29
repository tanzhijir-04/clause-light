"""Worker failure and evaluation semantics tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from server.core.llm import StructuredLLMResponse
from server.core.workers.parser import ClauseItem
from server.core.workers.workers import analyze_dimension, analyze_dimension_with_context


def _clause() -> ClauseItem:
    return ClauseItem(
        id="1",
        type="payment",
        title="付款",
        text="验收后付款",
        relevance=["financial"],
    )


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
