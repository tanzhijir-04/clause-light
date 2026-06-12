"""Prompt 模板测试"""

from __future__ import annotations

import pytest

from server.core.prompts.analyze import analyze_prompt
from server.core.prompts.classify import classify_prompt
from server.core.prompts.score import score_prompt
from server.core.prompts.split import split_prompt
from server.core.prompts.suggest import suggest_prompt


class TestClassifyPrompt:
    """分类 Prompt 测试"""

    def test_returns_message_list(self):
        """测试返回消息列表"""
        result = classify_prompt("这是一份租赁合同")
        assert isinstance(result, list)
        assert len(result) == 2

    def test_system_message(self):
        """测试系统消息"""
        result = classify_prompt("合同内容")
        assert result[0]["role"] == "system"
        assert "合同分类" in result[0]["content"]

    def test_user_message_contains_text(self):
        """测试用户消息包含合同文本"""
        result = classify_prompt("甲方：张三\n乙方：李四")
        assert result[1]["role"] == "user"
        assert "甲方：张三" in result[1]["content"]

    def test_text_truncation(self):
        """测试文本截断"""
        long_text = "测试" * 2000
        result = classify_prompt(long_text)
        # 应该被截断到 3000 字符
        assert len(result[1]["content"]) < 10000


class TestSplitPrompt:
    """条款拆解 Prompt 测试"""

    def test_returns_message_list(self):
        """测试返回消息列表"""
        result = split_prompt("合同全文", "租赁合同")
        assert isinstance(result, list)
        assert len(result) == 2

    def test_contains_contract_type(self):
        """测试包含合同类型"""
        result = split_prompt("合同全文", "劳动合同")
        assert "劳动合同" in result[1]["content"]

    def test_contains_contract_text(self):
        """测试包含合同文本"""
        result = split_prompt("合同全文内容", "租赁合同")
        assert "合同全文内容" in result[1]["content"]


class TestAnalyzePrompt:
    """风险分析 Prompt 测试"""

    def test_returns_message_list(self):
        """测试返回消息列表"""
        result = analyze_prompt(
            clause_content="条款内容",
            contract_type="租赁合同",
            contract_context="合同上下文",
            kb_rules=["规则1", "规则2"],
        )
        assert isinstance(result, list)
        assert len(result) == 2

    def test_contains_clause_content(self):
        """测试包含条款内容"""
        result = analyze_prompt(
            clause_content="违约金条款",
            contract_type="租赁合同",
            contract_context="上下文",
            kb_rules=[],
        )
        assert "违约金条款" in result[1]["content"]

    def test_contains_kb_rules(self):
        """测试包含知识库规则"""
        rules = ["违约金不应超过30%", "租赁期限不超过20年"]
        result = analyze_prompt(
            clause_content="条款",
            contract_type="租赁合同",
            contract_context="上下文",
            kb_rules=rules,
        )
        assert "违约金不应超过30%" in result[1]["content"]

    def test_empty_kb_rules(self):
        """测试空知识库规则"""
        result = analyze_prompt(
            clause_content="条款",
            contract_type="租赁合同",
            contract_context="上下文",
            kb_rules=[],
        )
        assert "无相关规则" in result[1]["content"]


class TestSuggestPrompt:
    """修改建议 Prompt 测试"""

    def test_returns_message_list(self):
        """测试返回消息列表"""
        result = suggest_prompt("条款内容", "违约金过高")
        assert isinstance(result, list)
        assert len(result) == 2

    def test_contains_clause_and_risk(self):
        """测试包含条款和风险类型"""
        result = suggest_prompt("违约金条款", "违约金过高")
        assert "违约金条款" in result[1]["content"]
        assert "违约金过高" in result[1]["content"]


class TestScorePrompt:
    """综合评分 Prompt 测试"""

    def test_returns_message_list(self):
        """测试返回消息列表"""
        analyses = [
            {"clause_number": "第一条", "clause_title": "目的", "risk_level": "green", "risk_summary": "正常", "severity_score": 1},
            {"clause_number": "第二条", "clause_title": "违约金", "risk_level": "red", "risk_summary": "过高", "severity_score": 8},
        ]
        result = score_prompt(analyses)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_contains_analysis_text(self):
        """测试包含分析文本"""
        analyses = [
            {"clause_number": "第一条", "clause_title": "目的", "risk_level": "green", "risk_summary": "正常", "severity_score": 1},
        ]
        result = score_prompt(analyses)
        assert "第一条" in result[1]["content"]
        assert "目的" in result[1]["content"]

    def test_empty_analyses(self):
        """测试空分析结果"""
        result = score_prompt([])
        assert isinstance(result, list)
