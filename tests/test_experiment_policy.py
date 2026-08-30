from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace

import pytest

from server.core.llm import LLMGateway


def _manifest_record(tmp_path, sample_id, independent_group, contract_type):
    input_file = tmp_path / f"{sample_id}.txt"
    input_file.write_text(f"{sample_id} text", encoding="utf-8")
    return {
        "sample_id": sample_id,
        "input_path": str(input_file),
        "contract_type": contract_type,
        "source_kind": "txt",
        "authorization_note": "test",
        "independent_group": independent_group,
        "contains_personal_data": False,
    }


@pytest.mark.asyncio
async def test_experiment_gateway_forces_frozen_request_parameters():
    with patch.object(LLMGateway, "__init__", return_value=None), patch.object(
        LLMGateway, "chat", new_callable=AsyncMock
    ) as parent_chat, patch.object(
        LLMGateway, "chat_structured", new_callable=AsyncMock
    ) as parent_structured:
        from experiments.contract_pipeline.policy import ExperimentGateway

        gateway = ExperimentGateway()
        await gateway.chat([], task="analysis", temperature=0.9, max_retries=2)
        await gateway.chat_structured(
            [], schema=object, task="analysis", temperature=0.9, max_retries=2
        )

    assert parent_chat.await_args.kwargs["temperature"] == 0.1
    assert parent_chat.await_args.kwargs["max_retries"] == 0
    assert parent_structured.await_args.kwargs["temperature"] == 0.1
    assert parent_structured.await_args.kwargs["max_retries"] == 0


def test_policy_freezes_ninety_plan_keys_and_three_mode_rotation():
    from experiments.contract_pipeline.policy import (
        EXPERIMENT_MAX_RETRIES,
        EXPERIMENT_TEMPERATURE,
        MODE_ORDER,
        PLANNED_RUNS,
        STRUCTURED_MODE,
    )

    assert PLANNED_RUNS == 6 * 3 * 5
    assert MODE_ORDER == (
        "single_pass",
        "serial_multi_stage",
        "parallel_multi_stage",
    )
    assert EXPERIMENT_TEMPERATURE == 0.1
    assert EXPERIMENT_MAX_RETRIES == 0
    assert STRUCTURED_MODE == "json_fallback"


def test_load_manifest_rejects_variants_that_would_create_more_than_90_plan_keys(tmp_path):
    from experiments.contract_pipeline.runner import load_manifest

    records = [
        _manifest_record(tmp_path, "rental-1", "rental-1", "rental"),
        _manifest_record(tmp_path, "rental-2", "rental-2", "rental"),
        _manifest_record(tmp_path, "labor-1", "labor-1", "labor"),
        _manifest_record(tmp_path, "labor-2", "labor-2", "labor"),
        _manifest_record(tmp_path, "service-1", "service-1", "service"),
        _manifest_record(tmp_path, "service-2", "service-2", "service"),
        _manifest_record(tmp_path, "rental-1-variant", "rental-1", "rental"),
    ]
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(
        "\n".join(json.dumps(record) for record in records),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="exactly 6 records"):
        load_manifest(manifest, require_comparison_set=True)


def test_load_manifest_without_comparison_gate_keeps_development_variants(tmp_path):
    from experiments.contract_pipeline.runner import load_manifest

    records = [
        _manifest_record(tmp_path, "rental-1", "rental-1", "rental"),
        _manifest_record(tmp_path, "rental-1-variant", "rental-1", "rental"),
    ]
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(
        "\n".join(json.dumps(record) for record in records),
        encoding="utf-8",
    )

    assert load_manifest(manifest, require_comparison_set=False) == records


def test_load_manifest_example_mode_remains_development_only():
    from experiments.contract_pipeline.runner import load_manifest

    records = load_manifest(
        "experiments/contract_pipeline/manifest.example.jsonl",
        require_comparison_set=False,
    )

    assert len(records) == 1


@pytest.mark.parametrize(
    ("lock_field", "locked_value"),
    [("provider_lock", "locked-provider"), ("model_lock", "locked-model")],
)
def test_preflight_rejects_lock_that_differs_from_actual_processing_plan(
    lock_field, locked_value
):
    from experiments.contract_pipeline.runner import preflight

    class FakeGateway:
        def get_processing_plan(self, task):
            return SimpleNamespace(
                provider="actual-provider",
                model="actual-model",
                processing_mode="local",
            )

    records = [{"independent_group": "g1", "contract_type": "rental"}]
    config = {
        "modes": ["single_pass", "serial_multi_stage", "parallel_multi_stage"],
        "runs_per_sample": 5,
        "temperature": 0.1,
        "max_retries": 0,
        "structured_mode": "json_fallback",
        lock_field: locked_value,
    }

    with pytest.raises(ValueError, match="不一致"):
        preflight(records, config, gateway=FakeGateway())


def test_protocol_check_rejects_result_without_call_trace():
    from experiments.contract_pipeline.runner import _protocol_failure

    result = SimpleNamespace(
        success=True,
        analysis_status="completed",
        overall_score=80,
        clauses=[{"risk_level": "green"}],
        review_reasons={},
        error_type="",
        error_message="",
        call_records=[],
    )

    checked = _protocol_failure(result, "provider", "model")

    assert checked.success is False
    assert checked.analysis_status == "failed"
    assert checked.error_type == "ProtocolViolation"


def test_preflight_reports_plan_count_and_known_estimate_without_call_cap(capsys):
    from experiments.contract_pipeline.runner import preflight

    class FakeGateway:
        def get_processing_plan(self, task):
            return SimpleNamespace(
                provider="local-provider",
                model="local-model",
                processing_mode="local",
            )

    records = [
        {"independent_group": f"g{i}", "contract_type": contract_type}
        for i, contract_type in enumerate(
            ["rental", "rental", "labor", "labor", "service", "service"]
        )
    ]
    config = {
        "modes": ["single_pass", "serial_multi_stage", "parallel_multi_stage"],
        "runs_per_sample": 5,
        "temperature": 0.1,
        "max_retries": 0,
        "structured_mode": "json_fallback",
    }

    preflight(records, config, gateway=FakeGateway())
    output = capsys.readouterr().out
    assert "planned_runs=90" in output
    assert "known_call_estimate=" in output
    assert "max_calls=" not in output
    assert "is_not_a_spend_cap=true" in output
