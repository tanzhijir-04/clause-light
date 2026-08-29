from __future__ import annotations

import pytest

from server.core.llm import StructuredLLMResponse
from server.core.schemas.llm_outputs import ClauseRiskListSchema, ClauseRiskSchema
from server.core.workers.parser import ClauseItem
from server.core.workers.workers import analyze_dimension


class FakeWorkerLLM:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error

    async def chat_structured(self, *args, **kwargs):
        if self.error:
            raise self.error
        return self.response

    def parse_json(self, content):
        return None


def _clause():
    return ClauseItem(id="1", type="payment", title="付款", text="付款条款", relevance=["financial"])


@pytest.mark.asyncio
@pytest.mark.parametrize("response, error", [
    (StructuredLLMResponse(content="", parsed=None), None),
    (StructuredLLMResponse(content="not-json", parsed=None), None),
    (None, RuntimeError("dimension exploded")),
])
async def test_worker_injected_failures_become_unknown_review(response, error):
    result = await analyze_dimension("financial", [_clause()], FakeWorkerLLM(response, error), "服务合同")
    assert len(result) == 1
    assert result[0].risk_level == "unknown"
    assert result[0].review_required is True
    assert result[0].analysis_status == "failed"


@pytest.mark.asyncio
async def test_forged_citation_is_captured_as_reviewable_result():
    response = StructuredLLMResponse(
        parsed=ClauseRiskListSchema(risks=[ClauseRiskSchema(
            clause_id="1", risk_level="yellow", citation_ids=["forged-law-id"]
        )]),
        content="{}",
    )
    clause = _clause()
    clause.law_references = [{"id": "real-law-id"}]
    result = await analyze_dimension("financial", [clause], FakeWorkerLLM(response), "服务合同")
    assert result[0].risk_level == "yellow"
    assert result[0].citation_ids == []
    assert result[0].review_required is True
    assert result[0].review_reason == "法条引用未通过校验"
