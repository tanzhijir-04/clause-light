from __future__ import annotations

from unittest.mock import AsyncMock, patch
from types import SimpleNamespace

import pytest

from server.core.llm import LLMGateway


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
