"""ClauseLight 正式对照实验的不可变执行策略。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel

from server.core.llm import LLMGateway, LLMResponse, StructuredLLMResponse

EXPERIMENT_TEMPERATURE = 0.1
EXPERIMENT_MAX_RETRIES = 0
STRUCTURED_MODE = "json_fallback"
MODE_ORDER = (
    "single_pass",
    "serial_multi_stage",
    "parallel_multi_stage",
)
PLANNED_INDEPENDENT_GROUPS = 6
PLANNED_REPEATS = 5
PLANNED_RUNS = PLANNED_INDEPENDENT_GROUPS * len(MODE_ORDER) * PLANNED_REPEATS


class ExperimentGateway(LLMGateway):
    """实验专用网关：不允许调用方覆盖协议中的温度和重试策略。"""

    def __init__(self, **kwargs) -> None:
        kwargs["structured_mode"] = STRUCTURED_MODE
        super().__init__(**kwargs)

    async def chat(self, messages: list[dict], **kwargs: Any) -> LLMResponse:
        kwargs["temperature"] = EXPERIMENT_TEMPERATURE
        kwargs["max_retries"] = EXPERIMENT_MAX_RETRIES
        return await super().chat(messages, **kwargs)

    async def chat_structured(
        self,
        messages: list[dict],
        schema: type[BaseModel],
        **kwargs: Any,
    ) -> StructuredLLMResponse:
        kwargs["temperature"] = EXPERIMENT_TEMPERATURE
        kwargs["max_retries"] = EXPERIMENT_MAX_RETRIES
        return await super().chat_structured(messages, schema=schema, **kwargs)


def rotate_modes(modes: Sequence[str], repeat_index: int) -> list[str]:
    """按重复轮次轮换模式先后顺序，保持计划键不变。"""
    ordered = list(modes)
    if not ordered:
        return []
    offset = (repeat_index - 1) % len(ordered)
    return ordered[offset:] + ordered[:offset]
