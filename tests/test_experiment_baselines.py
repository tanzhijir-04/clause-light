from __future__ import annotations

import hashlib
import json
import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from experiments.contract_pipeline import baselines
from server.core.agent import ContractAgent
from server.core.document_ingress import DocumentResult
from server.core.llm import StructuredLLMResponse
from server.core.workers.evaluator import EvaluationResult
from server.core.workers.parser import ClauseItem, ParseResult
from server.core.workers.workers import ClauseRisk


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
    assert "content" not in result.to_dict(store_contract_text=True)["clauses"][0]


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

        async def analyze(self, path, worker_mode, document_result, enable_memory):
            seen.append((worker_mode, document_result, enable_memory))
            return SimpleNamespace(
                analysis_status="completed",
                overall_score=80,
                clauses=[{"clause_number": "1", "content": "合同正文", "risk_level": "green"}],
                review_reasons={},
                error="",
            )

    document_result = await fake_ingest(input_file)
    monkeypatch.setattr(baselines, "ingest", pytest.fail)
    monkeypatch.setattr(baselines, "ContractAgent", FakeAgent)

    serial = await baselines.run_serial_multi_stage(
        str(input_file), FakeLLM(None), sample_id="s1", independent_group="g1",
        document_result=document_result,
    )
    parallel = await baselines.run_parallel_multi_stage(
        str(input_file), FakeLLM(None), sample_id="s1", independent_group="g1",
        document_result=document_result,
    )

    assert [item[0] for item in seen] == ["serial", "parallel"]
    assert all(item[1] is document_result for item in seen)
    assert all(item[2] is False for item in seen)
    assert serial.mode == "serial_multi_stage"
    assert parallel.mode == "parallel_multi_stage"
    assert serial.to_dict()["clauses"][0]["risk_level"] == "green"


def test_raw_serialization_keeps_only_redacted_whitelist():
    sentinel = "SENSITIVE-SENTINEL"
    result = baselines.ExperimentRunResult(
        experiment_id="exp",
        sample_id="sample",
        independent_group="group",
        mode="single_pass",
        repeat_index=1,
        provider="provider",
        model="model",
        temperature=0.1,
        started_at="2026-01-01T00:00:00+00:00",
        elapsed_ms=3,
        success=False,
        analysis_status="failed",
        overall_score=None,
        clauses=[{
            "clause_number": "1",
            "title": sentinel,
            "content": sentinel,
            "risk_level": "red",
            "risk_summary": sentinel,
            "suggested_clause": sentinel,
            "legal_basis": sentinel,
            "analysis_status": "failed",
            "needs_review": True,
            "source_start": 1,
            "source_end": 2,
        }],
        review_reasons={sentinel: [sentinel]},
        call_records=[{
            "task": "analysis",
            "provider": "provider",
            "model": "model",
            "temperature": 0.1,
            "attempt": 1,
            "latency_ms": 2,
            "input_tokens": 1,
            "output_tokens": 1,
            "tokens_used": 2,
            "success": False,
            "structured_via": "chat",
            "error_message": sentinel,
        }],
        estimated_cost=None,
        cost_currency="USD",
        input_sha256="hash",
        error_type="TimeoutError",
        error_message=sentinel,
    )

    serialized = result.to_dict(store_contract_text=True)
    assert sentinel not in str(serialized)
    assert set(serialized["clauses"][0]) == {
        "clause_number", "risk_level", "analysis_status", "needs_review",
        "source_start", "source_end",
    }
    assert all("error_message" not in record for record in serialized["call_records"])
    assert serialized["review_reasons"] == {"pipeline": 1}


def test_failed_terminal_key_is_skipped_during_resume(tmp_path):
    from experiments.contract_pipeline import runner

    output = tmp_path / "result.jsonl"
    output.write_text(json.dumps({
        "experiment_id": "exp",
        "sample_id": "s1",
        "mode": "single_pass",
        "repeat_index": 1,
        "success": False,
    }) + "\n", encoding="utf-8")

    assert ("exp", "s1", "single_pass", 1) in runner._existing_keys(
        output, include_failed=False
    )


@pytest.mark.asyncio
async def test_timeout_is_written_as_a_complete_failed_result(tmp_path, monkeypatch):
    from experiments.contract_pipeline import runner

    input_file = tmp_path / "contract.txt"
    input_file.write_text("真实正文不应被伪造", encoding="utf-8")
    output = tmp_path / "result.jsonl"

    async def fake_ingest(path):
        return SimpleNamespace(full_text="规范化正文", confidence_avg=1.0)

    class FakeGateway:
        def __init__(self, **kwargs):
            self._trace_sink = kwargs.get("trace_sink")

    async def never_finishes(*args, **kwargs):
        await asyncio.sleep(0.05)

    monkeypatch.setattr(runner, "ingest", fake_ingest)
    monkeypatch.setattr(runner, "ExperimentGateway", FakeGateway)
    monkeypatch.setattr(runner, "run_mode", never_finishes)

    args = SimpleNamespace(output=str(output), include_failed=False)
    records = [{
        "sample_id": "s1",
        "input_path": str(input_file),
        "contract_type": "rental",
        "source_kind": "txt",
        "authorization_note": "test",
        "independent_group": "g1",
        "contains_personal_data": False,
    }]
    config = {
        "modes": ["single_pass"],
        "runs_per_sample": 1,
        "temperature": 0.1,
        "timeout_seconds": 0.01,
        "pricing": None,
        "structured_mode": "json_fallback",
    }

    await runner._run(args, records, config, "provider", "model")

    line = output.read_text(encoding="utf-8").strip()
    assert line
    item = __import__("json").loads(line)
    assert item["success"] is False
    assert item["analysis_status"] == "failed"
    assert item["overall_score"] is None
    assert item["clauses"] == []
    assert item["error_type"] == "TimeoutError"
    assert item["error_message"] == ""
    assert item["elapsed_ms"] > 0
    assert "真实正文不应被伪造" not in line


@pytest.mark.asyncio
async def test_runner_writes_failure_for_each_plan_key_when_preparse_ingest_fails(
    tmp_path, monkeypatch
):
    from experiments.contract_pipeline import runner

    input_file = tmp_path / "contract.jsonl"
    input_file.write_text('{"private":"text"}\n', encoding="utf-8")
    output = tmp_path / "result.jsonl"
    run_mode_calls = []
    gateway_requests = []

    async def failing_ingest(path):
        raise RuntimeError("ingest failed")

    class FakeGateway:
        def __init__(self, **kwargs):
            self._trace_sink = kwargs.get("trace_sink")

        async def chat(self, *args, **kwargs):
            gateway_requests.append("chat")
            raise AssertionError("model request must not be sent")

        async def chat_structured(self, *args, **kwargs):
            gateway_requests.append("chat_structured")
            raise AssertionError("model request must not be sent")

    async def unexpected_run_mode(*args, **kwargs):
        run_mode_calls.append((args, kwargs))
        raise AssertionError("run_mode must not be called after pre-parse failure")

    monkeypatch.setattr(runner, "ingest", failing_ingest)
    monkeypatch.setattr(runner, "ExperimentGateway", FakeGateway)
    monkeypatch.setattr(runner, "run_mode", unexpected_run_mode)

    args = SimpleNamespace(output=str(output), include_failed=False)
    records = [{
        "sample_id": "s1",
        "input_path": str(input_file),
        "contract_type": "rental",
        "source_kind": "txt",
        "authorization_note": "test",
        "independent_group": "g1",
        "contains_personal_data": False,
    }]
    config = {
        "modes": ["single_pass", "serial_multi_stage", "parallel_multi_stage"],
        "runs_per_sample": 2,
        "temperature": 0.1,
        "timeout_seconds": 1,
        "pricing": None,
        "structured_mode": "json_fallback",
    }

    await runner._run(args, records, config, "provider", "model")

    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 6
    assert {(row["mode"], row["repeat_index"]) for row in rows} == {
        ("single_pass", 1),
        ("serial_multi_stage", 1),
        ("parallel_multi_stage", 1),
        ("single_pass", 2),
        ("serial_multi_stage", 2),
        ("parallel_multi_stage", 2),
    }
    assert all(row["success"] is False for row in rows)
    assert all(row["analysis_status"] == "failed" for row in rows)
    assert all(row["error_type"] == "RuntimeError" for row in rows)
    assert all(row["sample_id"] == "s1" and row["independent_group"] == "g1" for row in rows)
    assert run_mode_calls == []
    assert gateway_requests == []


@pytest.mark.asyncio
async def test_runner_parses_each_sample_once_rotates_modes_and_reuses_hash(tmp_path, monkeypatch):
    from experiments.contract_pipeline import runner

    input_file = tmp_path / "contract.txt"
    input_file.write_text("原始\n正文", encoding="utf-8")
    output = tmp_path / "result.jsonl"
    parse_calls = 0
    seen = []

    async def fake_ingest(path):
        nonlocal parse_calls
        parse_calls += 1
        return SimpleNamespace(full_text="规范化\n正文", confidence_avg=1.0)

    class FakeGateway:
        def __init__(self, **kwargs):
            pass

    async def fake_run_mode(mode, value, gateway, **kwargs):
        seen.append((mode, value, kwargs.get("document_result")))
        return baselines.ExperimentRunResult(
            experiment_id="placeholder",
            sample_id=kwargs["sample_id"],
            independent_group=kwargs["independent_group"],
            mode=mode,
            repeat_index=kwargs["repeat_index"],
            provider="provider",
            model="model",
            temperature=0.1,
            started_at="now",
            elapsed_ms=1,
            success=True,
            analysis_status="completed",
            overall_score=80,
            clauses=[],
            review_reasons={},
            call_records=[{
                "provider": "provider",
                "model": "model",
                "temperature": 0.1,
            }],
            estimated_cost=None,
            cost_currency="",
            input_sha256=hashlib.sha256("规范化 正文".encode()).hexdigest(),
            parse_elapsed_ms=kwargs["parse_elapsed_ms"],
        )

    monkeypatch.setattr(runner, "ingest", fake_ingest)
    monkeypatch.setattr(runner, "ExperimentGateway", FakeGateway)
    monkeypatch.setattr(runner, "run_mode", fake_run_mode)

    args = SimpleNamespace(output=str(output), include_failed=False)
    records = [{
        "sample_id": "s1",
        "input_path": str(input_file),
        "contract_type": "rental",
        "source_kind": "txt",
        "authorization_note": "test",
        "independent_group": "g1",
        "contains_personal_data": False,
    }]
    config = {
        "modes": ["single_pass", "serial_multi_stage", "parallel_multi_stage"],
        "runs_per_sample": 2,
        "temperature": 0.1,
        "timeout_seconds": 1,
        "pricing": None,
        "structured_mode": "json_fallback",
    }

    await runner._run(args, records, config, "provider", "model")

    assert parse_calls == 1
    assert [item[0] for item in seen] == [
        "single_pass", "serial_multi_stage", "parallel_multi_stage",
        "serial_multi_stage", "parallel_multi_stage", "single_pass",
    ]
    assert seen[0][1] == "规范化 正文"
    assert seen[1][1] == str(input_file)
    assert seen[1][2] is seen[2][2]
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert len({row["input_sha256"] for row in rows}) == 1
    assert all(row["parse_elapsed_ms"] >= 0 for row in rows)


@pytest.mark.asyncio
async def test_experiment_agent_skips_ingest_memory_tools_and_distill(db_session):
    document_result = DocumentResult(full_text="租期一年", markdown="租期一年", confidence_avg=1.0)
    parse_result = ParseResult(
        contract_type="租赁合同",
        contract_type_en="rental",
        complexity="standard",
        recommended_model="fast",
        clauses=[ClauseItem(id="1", type="termination", title="期限", text="租期一年", relevance=["equity"])],
    )

    async def fake_dimension(dim, clauses, llm, contract_type, kb_rules=None, kb_laws=None, memory_context=""):
        if dim == "equity":
            return [ClauseRisk(clause_id="1", risk_level="green", issue="ok", severity=1)]
        return []

    @asynccontextmanager
    async def factory():
        yield db_session

    agent = ContractAgent(llm=AsyncMock(), ocr=AsyncMock())
    with (
        patch("server.core.agent.document_ingress.ingest", new_callable=AsyncMock, side_effect=AssertionError("ingest")) as ingest_mock,
        patch("server.core.agent.parse_contract", new_callable=AsyncMock, return_value=parse_result),
        patch("server.core.agent.analyze_dimension", side_effect=fake_dimension),
        patch("server.core.agent.evaluate", new_callable=AsyncMock, return_value=EvaluationResult(
            overall_score=80,
            risk_distribution={"red": 0, "yellow": 0, "green": 1},
            recommendation="sign",
            one_line_summary="ok",
        )),
        patch("server.core.agent.async_session_factory", factory),
        patch("server.core.knowledge.KnowledgeEngine.search", new_callable=AsyncMock, return_value=[]),
        patch("server.core.knowledge.KnowledgeEngine.search_laws", new_callable=AsyncMock, return_value=[]),
        patch("server.core.memory.kernel.MemoryKernel.start_session", new_callable=AsyncMock, side_effect=AssertionError("memory")) as start_session,
        patch("server.core.agent_tools.build_loadout", new_callable=AsyncMock, side_effect=AssertionError("loadout")) as build_loadout,
        patch("server.core.agent_tools.run_conflict_tools", new_callable=AsyncMock, side_effect=AssertionError("conflict")) as conflict_tools,
        patch("server.core.distill.pipeline.distill_from_analysis", new_callable=AsyncMock, side_effect=AssertionError("distill")) as distill,
    ):
        result = await agent.analyze(
            "private.pdf",
            document_result=document_result,
            enable_memory=False,
        )

    assert result.analysis_status == "completed"
    ingest_mock.assert_not_awaited()
    start_session.assert_not_awaited()
    build_loadout.assert_not_awaited()
    conflict_tools.assert_not_awaited()
    distill.assert_not_awaited()
