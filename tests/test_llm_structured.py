"""Outlines / chat_structured 结构化输出测试"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from server.core.llm import LLMGateway, StructuredLLMResponse
from server.core.schemas.llm_outputs import (
    ClauseRiskListSchema,
    EvaluationSchema,
    ParseResultSchema,
)


class _Tiny(BaseModel):
    name: str
    score: int = 1


class TestValidateSchema:
    def setup_method(self):
        self.gw = LLMGateway()
        self.gw._clients = {}

    def test_validate_object(self):
        raw = '{"name": "合同", "score": 3}'
        parsed = self.gw._validate_schema(raw, _Tiny)
        assert parsed is not None
        assert parsed.name == "合同"
        assert parsed.score == 3

    def test_validate_wraps_list_into_single_field(self):
        raw = '[{"clause_id": "1", "risk_level": "red", "severity": 8}]'
        parsed = self.gw._validate_schema(raw, ClauseRiskListSchema)
        assert parsed is not None
        assert len(parsed.risks) == 1
        assert parsed.risks[0].risk_level == "red"

    def test_validate_rejects_bad_enum(self):
        raw = '{"overall_score": 50, "recommendation": "maybe"}'
        parsed = self.gw._validate_schema(raw, EvaluationSchema)
        assert parsed is None


@pytest.mark.asyncio
async def test_chat_structured_fallback_when_outlines_disabled(monkeypatch):
    gw = LLMGateway()
    gw._clients = {}

    monkeypatch.setattr("server.core.llm.settings.OUTLINES_ENABLED", False)

    async def fake_chat(messages, task="analysis", temperature=0.1, max_retries=2):
        from server.core.llm import LLMResponse

        return LLMResponse(
            content='{"contract_type":"租赁合同","complexity":"standard","clauses":[]}',
            model="m",
            provider="p",
        )

    gw.chat = fake_chat  # type: ignore
    result = await gw.chat_structured(
        [{"role": "user", "content": "x"}],
        schema=ParseResultSchema,
        task="analysis",
    )
    assert result.via == "fallback"
    assert isinstance(result.parsed, ParseResultSchema)
    assert result.parsed.contract_type == "租赁合同"


@pytest.mark.asyncio
async def test_chat_structured_uses_outlines_when_available(monkeypatch):
    gw = LLMGateway()
    client = MagicMock()
    gw._clients = {"deepseek": client}
    gw._config = {
        "remote": {"enabled": True, "provider": "deepseek", "models": {"analyze": "deepseek-chat"}},
        "local": {"enabled": False},
    }
    monkeypatch.setattr("server.core.llm.settings.OUTLINES_ENABLED", True)
    monkeypatch.setattr(
        "server.core.llm.settings.LLM_DEEPSEEK_API_KEY",
        "sk-test",
        raising=False,
    )

    class FakeOutlinesModel:
        async def __call__(self, chat_input, schema, **kwargs):
            return ParseResultSchema(
                contract_type="劳动合同",
                complexity="standard",
                clauses=[],
            )

    def fake_from_openai(c, model_name):
        return FakeOutlinesModel()

    with patch.dict("sys.modules", {}):
        import outlines

        monkeypatch.setattr(outlines, "from_openai", fake_from_openai)
        # ensure providers list non-empty
        monkeypatch.setattr(
            gw,
            "_get_available_providers",
            lambda: ["deepseek"],
        )
        monkeypatch.setattr(gw, "_get_model", lambda p, t: "deepseek-chat")

        result = await gw.chat_structured(
            [{"role": "user", "content": "解析"}],
            schema=ParseResultSchema,
            task="analysis",
        )

    assert result.via == "outlines"
    assert result.parsed is not None
    assert result.parsed.contract_type == "劳动合同"
