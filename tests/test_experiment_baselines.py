from __future__ import annotations

from types import SimpleNamespace

import pytest

from experiments.contract_pipeline import baselines
from server.core.llm import StructuredLLMResponse


class FakeLLM:
    def __init__(self, parsed):
        self.parsed = parsed
        self.calls = []

    async def chat_structured(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return StructuredLLMResponse(
            content="{}" if self.parsed is None else self.parsed.model_dump_json(),
            model="fake-model",
            provider="fake-provider",
            parsed=self.parsed,
            via="fallback",
        )

    def parse_json(self, content):
        return {}


def _single_pass_result():
    clause = baselines.SinglePassClauseSchema(
        clause_number="1",
        title="付款",
        content="甲方应在交付后付款。",
        type="payment",
        risk_level="yellow",
        risk_summary="付款条件需要协商",
    )
    return baselines.SinglePassReviewSchema(
        contract_type="服务合同",
        overall_score=60,
        recommendation="negotiate_first",
        clauses=[clause],
    )


@pytest.mark.asyncio
async def test_single_pass_is_one_whole_document_call_and_redacts_text():
    llm = FakeLLM(_single_pass_result())
    result = await baselines.run_single_pass(
        "甲方应在交付后付款。",
        llm,
        sample_id="s1",
        independent_group="g1",
    )

    assert result.mode == "single_pass"
    assert result.success is True
    assert len(llm.calls) == 1
    assert result.clauses[0]["risk_level"] == "yellow"
    assert "content" not in result.to_dict()["clauses"][0]
    assert result.to_dict(store_contract_text=True)["clauses"][0]["content"]


@pytest.mark.asyncio
async def test_single_pass_structured_failure_is_explicit():
    llm = FakeLLM(None)
    result = await baselines.run_single_pass(
        "合同正文",
        llm,
        sample_id="s1",
        independent_group="g1",
    )

    assert result.success is False
    assert result.analysis_status == "failed"
    assert result.error_type == "ValueError"
    assert result.review_reasons["pipeline"]


@pytest.mark.asyncio
async def test_multi_stage_modes_share_agent_and_only_change_worker_mode(monkeypatch, tmp_path):
    input_file = tmp_path / "contract.txt"
    input_file.write_text("合同正文", encoding="utf-8")
    seen = []

    async def fake_ingest(path):
        return SimpleNamespace(full_text="合同正文")

    class FakeAgent:
        def __init__(self, llm):
            self.llm = llm

        async def analyze(self, path, worker_mode):
            seen.append(worker_mode)
            return SimpleNamespace(
                analysis_status="completed",
                overall_score=80,
                clauses=[{"clause_number": "1", "content": "合同正文", "risk_level": "green"}],
                review_reasons={},
                error="",
            )

    monkeypatch.setattr(baselines, "ingest", fake_ingest)
    monkeypatch.setattr(baselines, "ContractAgent", FakeAgent)

    serial = await baselines.run_serial_multi_stage(
        str(input_file), FakeLLM(None), sample_id="s1", independent_group="g1"
    )
    parallel = await baselines.run_parallel_multi_stage(
        str(input_file), FakeLLM(None), sample_id="s1", independent_group="g1"
    )

    assert seen == ["serial", "parallel"]
    assert serial.mode == "serial_multi_stage"
    assert parallel.mode == "parallel_multi_stage"
    assert serial.to_dict()["clauses"][0]["risk_level"] == "green"
