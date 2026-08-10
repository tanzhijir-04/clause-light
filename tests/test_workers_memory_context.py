"""维度 Worker 记忆上下文注入测试"""

from __future__ import annotations

import json

import pytest

from server.core.workers.parser import ClauseItem
from server.core.workers.workers import analyze_dimension


@pytest.mark.asyncio
async def test_analyze_dimension_includes_memory_context():
    """memory_context 非空时应出现在 LLM messages 中"""
    captured: dict = {}

    class FakeLLM:
        def parse_json(self, content: str):
            return []

        async def chat(self, messages, task="analysis", **kwargs):
            captured["messages"] = messages

            class R:
                content = "[]"

            return R()

    clauses = [
        ClauseItem(
            id="1",
            type="payment",
            title="付款",
            text="验收后90日付款",
            relevance=["financial"],
        )
    ]
    await analyze_dimension(
        "financial",
        clauses,
        FakeLLM(),
        "租赁合同",
        [],
        [],
        memory_context="用户是乙方",
    )
    blob = json.dumps(captured["messages"], ensure_ascii=False)
    assert "用户是乙方" in blob


@pytest.mark.asyncio
async def test_analyze_dimension_omits_empty_memory_context():
    """空 memory_context 不应注入记忆段落标题"""
    captured: dict = {}

    class FakeLLM:
        def parse_json(self, content: str):
            return []

        async def chat(self, messages, task="analysis", **kwargs):
            captured["messages"] = messages

            class R:
                content = "[]"

            return R()

    clauses = [
        ClauseItem(
            id="1",
            type="payment",
            title="付款",
            text="验收后90日付款",
            relevance=["financial"],
        )
    ]
    await analyze_dimension(
        "financial",
        clauses,
        FakeLLM(),
        "租赁合同",
        [],
        [],
        memory_context="",
    )
    blob = json.dumps(captured["messages"], ensure_ascii=False)
    assert "记忆与知识" not in blob
