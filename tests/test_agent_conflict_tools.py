"""冲突路径按需调用 memory/wiki/skill 工具测试"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest

from server.core.agent import ContractAgent
from server.core.agent_tools import ToolBundle
from server.core.document_ingress import DocumentResult
from server.core.workers.evaluator import EvaluationResult
from server.core.workers.parser import ClauseItem, ParseResult
from server.core.workers.workers import ClauseRisk


def _make_doc(text: str) -> DocumentResult:
    return DocumentResult(
        full_text=text,
        markdown=text,
        source="paddle",
        confidence_avg=0.95,
    )


@pytest.mark.asyncio
async def test_conflict_path_passes_wiki_into_resolve(db_session):
    """冲突时 run_conflict_tools 的 wiki 文本应进入 analyze_dimension_with_context。"""
    captured_memory: list[str] = []
    tool_calls = {"n": 0}

    async def _fake_conflict_tools(db, *, query, contract_type):
        tool_calls["n"] += 1
        return ToolBundle(
            memory_text="",
            wiki_text="### Wiki\n- **民法典**: 违约金约定过高可请求调整",
            skill_text="",
        )

    async def _fake_with_context(
        dimension,
        clause,
        llm,
        contract_type,
        cross_context,
        kb_rules=None,
        kb_laws=None,
        memory_context="",
    ):
        captured_memory.append(memory_context or "")
        return ClauseRisk(
            clause_id=clause.id,
            risk_level="yellow",
            risk_type="裁决",
            issue="协调后黄灯",
            severity=5,
        )

    async def _fake_dimension(
        dim, clauses, llm, contract_type, kb_rules=None, kb_laws=None, memory_context=""
    ):
        # 同条款 red+green → 触发冲突
        if dim == "equity":
            return [
                ClauseRisk(
                    clause_id="1",
                    risk_level="red",
                    risk_type="权责",
                    issue="不对等",
                    severity=8,
                )
            ]
        if dim == "financial":
            return [
                ClauseRisk(
                    clause_id="1",
                    risk_level="green",
                    risk_type="财务",
                    issue="无风险",
                    severity=1,
                )
            ]
        return []

    @asynccontextmanager
    async def _factory():
        yield db_session

    parse_result = ParseResult(
        contract_type="租赁合同",
        contract_type_en="rental",
        complexity="standard",
        recommended_model="fast",
        clauses=[
            ClauseItem(
                id="1",
                type="penalty",
                title="违约金",
                text="违约金为月租金的50%",
                relevance=["equity", "financial"],
            )
        ],
    )

    agent = ContractAgent(llm=AsyncMock(), ocr=AsyncMock())

    with (
        patch(
            "server.core.agent.document_ingress.ingest",
            new_callable=AsyncMock,
            return_value=_make_doc("租赁合同 违约金"),
        ),
        patch("server.core.agent.parse_contract", new_callable=AsyncMock, return_value=parse_result),
        patch("server.core.agent.analyze_dimension", side_effect=_fake_dimension),
        patch(
            "server.core.agent.analyze_dimension_with_context",
            side_effect=_fake_with_context,
        ),
        patch(
            "server.core.agent_tools.run_conflict_tools",
            side_effect=_fake_conflict_tools,
        ),
        patch(
            "server.core.agent.evaluate",
            new_callable=AsyncMock,
            return_value=EvaluationResult(
                overall_score=55,
                risk_distribution={"red": 0, "yellow": 1, "green": 0},
                recommendation="negotiate_first",
                one_line_summary="有冲突已协调",
            ),
        ),
        patch("server.core.agent.async_session_factory", _factory),
        patch(
            "server.core.knowledge.KnowledgeEngine.search",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "server.core.knowledge.KnowledgeEngine.search_laws",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        result = await agent.analyze(file_path="test.pdf")

    assert result.error == ""
    assert tool_calls["n"] == 1
    assert captured_memory
    assert "民法典" in captured_memory[0] or "Wiki" in captured_memory[0]


@pytest.mark.asyncio
async def test_conflict_tools_budget_max_two(db_session):
    """冲突条款簇超过 2 个时，工具最多调用 2 次。"""
    tool_calls = {"n": 0}

    async def _fake_conflict_tools(db, *, query, contract_type):
        tool_calls["n"] += 1
        return ToolBundle(wiki_text=f"wiki-{tool_calls['n']}")

    async def _fake_with_context(*args, memory_context="", **kwargs):
        clause = args[1] if len(args) > 1 else kwargs.get("clause")
        return ClauseRisk(
            clause_id=clause.id,
            risk_level="yellow",
            risk_type="裁决",
            issue="ok",
            severity=4,
        )

    async def _fake_dimension(
        dim, clauses, llm, contract_type, kb_rules=None, kb_laws=None, memory_context=""
    ):
        risks = []
        if dim == "equity":
            for c in clauses:
                risks.append(
                    ClauseRisk(
                        clause_id=c.id,
                        risk_level="red",
                        risk_type="权责",
                        issue="红",
                        severity=8,
                    )
                )
        if dim == "financial":
            for c in clauses:
                risks.append(
                    ClauseRisk(
                        clause_id=c.id,
                        risk_level="green",
                        risk_type="财务",
                        issue="绿",
                        severity=1,
                    )
                )
        return risks

    @asynccontextmanager
    async def _factory():
        yield db_session

    clauses = [
        ClauseItem(
            id=str(i),
            type="penalty",
            title=f"条款{i}",
            text=f"文本{i}",
            relevance=["equity", "financial"],
        )
        for i in range(1, 4)
    ]
    parse_result = ParseResult(
        contract_type="租赁合同",
        contract_type_en="rental",
        complexity="standard",
        recommended_model="fast",
        clauses=clauses,
    )

    agent = ContractAgent(llm=AsyncMock(), ocr=AsyncMock())

    with (
        patch(
            "server.core.agent.document_ingress.ingest",
            new_callable=AsyncMock,
            return_value=_make_doc("租赁合同"),
        ),
        patch("server.core.agent.parse_contract", new_callable=AsyncMock, return_value=parse_result),
        patch("server.core.agent.analyze_dimension", side_effect=_fake_dimension),
        patch(
            "server.core.agent.analyze_dimension_with_context",
            side_effect=_fake_with_context,
        ),
        patch(
            "server.core.agent_tools.run_conflict_tools",
            side_effect=_fake_conflict_tools,
        ),
        patch(
            "server.core.agent.evaluate",
            new_callable=AsyncMock,
            return_value=EvaluationResult(
                overall_score=50,
                risk_distribution={"red": 0, "yellow": 3, "green": 0},
                recommendation="negotiate_first",
                one_line_summary="多冲突",
            ),
        ),
        patch("server.core.agent.async_session_factory", _factory),
        patch(
            "server.core.knowledge.KnowledgeEngine.search",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "server.core.knowledge.KnowledgeEngine.search_laws",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        result = await agent.analyze(file_path="test.pdf")

    assert result.error == ""
    assert tool_calls["n"] == 2
