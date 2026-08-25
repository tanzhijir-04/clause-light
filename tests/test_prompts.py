"""当前 Prompt 构建器测试"""

from __future__ import annotations

from server.core.distill.pipeline import build_distill_messages
from server.core.workers.workers import build_worker_system_prompt


class TestWorkerPrompt:
    """当前五维 Worker Prompt 测试"""

    def test_returns_prompt_for_each_dimension(self):
        """每个风险维度都能生成非空系统 Prompt"""
        dimensions = ["equity", "financial", "ip", "dispute", "general"]

        for dimension in dimensions:
            prompt = build_worker_system_prompt(dimension)
            assert isinstance(prompt, str)
            assert prompt
            assert "risk_level" in prompt

    def test_financial_prompt_contains_dimension_focus(self):
        """财务 Worker Prompt 包含财务风险关注点"""
        prompt = build_worker_system_prompt("financial")

        assert "财务风险" in prompt
        assert "付款周期" in prompt
        assert "违约金" in prompt

    def test_worker_prompt_requires_structured_json(self):
        """Worker Prompt 要求统一 JSON 字段"""
        prompt = build_worker_system_prompt("equity")

        assert "clause_id" in prompt
        assert "suggestion" in prompt
        assert "legal_basis" in prompt


class TestDistillPrompt:
    """分析结果记忆提炼 Prompt 测试"""

    def test_returns_two_messages(self):
        """Distill Prompt 返回 system/user 两条消息"""
        result = build_distill_messages(
            contract_type="租赁合同",
            clause_summaries=[],
        )

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["role"] == "system"
        assert result[1]["role"] == "user"

    def test_contains_contract_type_and_clause_summary(self):
        """Distill Prompt 包含合同类型和条款摘要"""
        result = build_distill_messages(
            contract_type="租赁合同",
            clause_summaries=[
                {
                    "clause_id": "3",
                    "title": "付款条款",
                    "risk_level": "red",
                    "risk_summary": "违约金过高",
                }
            ],
        )

        assert "租赁合同" in result[1]["content"]
        assert "付款条款" in result[1]["content"]
        assert "违约金过高" in result[1]["content"]

    def test_feedback_events_default_to_empty_list(self):
        """未提供反馈事件时，Prompt 使用空反馈列表"""
        result = build_distill_messages(
            contract_type="其他",
            clause_summaries=[],
        )

        assert '"feedback_events": []' in result[1]["content"]
