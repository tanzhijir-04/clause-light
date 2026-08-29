"""Worker failure and evaluation semantics tests."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from server.core.llm import StructuredLLMResponse
from server.core.workers.parser import ClauseItem
from server.core.workers.workers import analyze_dimension


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
    llm = AsyncMock()
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
    llm = AsyncMock()
    llm.chat_structured.return_value = StructuredLLMResponse(
        content="not json", parsed=None
    )
    llm.parse_json.return_value = None

    results = await analyze_dimension("financial", [_clause()], llm, "服务合同")

    assert len(results) == 1
    risk = results[0]
    assert risk.risk_level == "unknown"
    assert risk.analysis_status == "failed"
    assert risk.review_required is True
    assert "financial" in risk.review_reason
