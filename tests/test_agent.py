"""Agent Harness 测试"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.core.agent import AnalysisResult, ContractAgent, TYPE_EN_MAP


class TestAnalysisResult:
    """分析结果数据类测试"""

    def test_default_values(self):
        """测试默认值"""
        result = AnalysisResult()
        assert result.contract_id == ""
        assert result.overall_score == 0
        assert result.clauses == []
        assert result.red_count == 0

    def test_custom_values(self):
        """测试自定义值"""
        result = AnalysisResult(
            contract_id="test_id",
            contract_type="租赁合同",
            overall_score=85,
            clauses=[{"clause_number": "第一条"}],
            red_count=1,
            yellow_count=2,
            green_count=5,
        )
        assert result.contract_id == "test_id"
        assert len(result.clauses) == 1


class TestTypeEnMap:
    """类型映射测试"""

    def test_known_types(self):
        """测试已知类型映射"""
        assert TYPE_EN_MAP["租赁合同"] == "rental"
        assert TYPE_EN_MAP["劳动合同"] == "labor"
        assert TYPE_EN_MAP["装修合同"] == "renovation"
        assert TYPE_EN_MAP["外包合同"] == "outsourcing"

    def test_unknown_type(self):
        """测试未知类型"""
        assert TYPE_EN_MAP.get("未知类型", "other") == "other"


class TestContractAgent:
    """合同分析 Agent 测试"""

    def setup_method(self):
        """初始化 Mock 对象"""
        self.mock_llm = MagicMock()
        self.mock_ocr = MagicMock()
        self.agent = ContractAgent(llm=self.mock_llm, ocr=self.mock_ocr)

    async def test_analyze_empty_ocr(self):
        """测试 OCR 返回空结果"""
        mock_result = MagicMock()
        mock_result.full_text = ""
        self.mock_ocr.recognize = AsyncMock(return_value=mock_result)

        result = await self.agent.analyze(file_path="test.pdf")
        assert result.contract_id == ""  # 空文本时提前返回

    async def test_analyze_with_text(self):
        """测试正常分析流程（无类型提示）"""
        mock_ocr_result = MagicMock()
        mock_ocr_result.full_text = "租赁合同\n甲方：张三\n乙方：李四\n第一条 租赁期限"
        self.mock_ocr.recognize = AsyncMock(return_value=mock_ocr_result)

        # chat 调用顺序: Step 2 classify, Step 3 split, Step 5 analyze, Step 7 score
        classify_resp = MagicMock()
        classify_resp.content = "租赁合同"
        classify_resp.model = "deepseek-chat"

        split_resp = MagicMock()
        split_resp.content = "split_resp"
        split_resp.model = "deepseek-chat"

        analyze_resp = MagicMock()
        analyze_resp.content = "analyze_resp"
        analyze_resp.model = "deepseek-chat"

        score_resp = MagicMock()
        score_resp.content = "score_resp"
        score_resp.model = "deepseek-chat"

        self.mock_llm.chat = AsyncMock(
            side_effect=[classify_resp, split_resp, analyze_resp, score_resp]
        )

        # parse_json 调用顺序: Step 3 split, Step 5 analyze, Step 7 score
        # 注意: Step 2 (classify) 不调用 parse_json
        self.mock_llm.parse_json = MagicMock(
            side_effect=[
                [{"clause_number": "第一条", "title": "租赁期限", "content": "租赁期限为一年"}],
                {"risk_level": "green", "risk_type": "无风险", "risk_summary": "正常条款",
                 "plain_explanation": "正常", "legal_basis": "《合同法》", "severity_score": 1},
                {"overall_score": 85, "risk_distribution": {"red": 0, "yellow": 0, "green": 1},
                 "one_line_summary": "合同风险可控", "recommendation": "sign"},
            ]
        )

        with patch("server.core.agent.async_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await self.agent.analyze(file_path="test.pdf")
            assert result.overall_score == 85
            assert result.contract_type == "租赁合同"
            assert len(result.clauses) == 1

    async def test_analyze_with_hint_preserves_hint_when_classify_fails(self):
        """测试带类型提示：classify 失败时保留 hint"""
        mock_ocr_result = MagicMock()
        mock_ocr_result.full_text = "劳动合同内容..."
        self.mock_ocr.recognize = AsyncMock(return_value=mock_ocr_result)

        # classify 失败, split 正常
        classify_resp = MagicMock()
        classify_resp.content = ""  # 空内容，保留 hint
        classify_resp.model = "deepseek-chat"

        split_resp = MagicMock()
        split_resp.content = "split_resp"
        split_resp.model = "deepseek-chat"

        analyze_resp = MagicMock()
        analyze_resp.content = "analyze_resp"
        analyze_resp.model = "deepseek-chat"

        score_resp = MagicMock()
        score_resp.content = "score_resp"
        score_resp.model = "deepseek-chat"

        self.mock_llm.chat = AsyncMock(
            side_effect=[classify_resp, split_resp, analyze_resp, score_resp]
        )

        self.mock_llm.parse_json = MagicMock(
            side_effect=[
                [{"clause_number": "第一条", "content": "试用期三个月"}],
                {"risk_level": "yellow", "risk_type": "试用期过长",
                 "risk_summary": "试用期超过法定上限", "plain_explanation": "试用期太长了",
                 "legal_basis": "《劳动合同法》", "severity_score": 6},
                {"overall_score": 60, "risk_distribution": {"red": 0, "yellow": 1, "green": 0},
                 "one_line_summary": "试用期条款需修改", "recommendation": "negotiate_first"},
            ]
        )

        with patch("server.core.agent.async_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await self.agent.analyze(
                file_path="test.pdf",
                contract_type_hint="劳动合同",
            )
            # hint 作为默认值，classify 返回空所以保留 hint
            assert result.contract_type == "劳动合同"
            assert result.overall_score == 60

    async def test_analyze_with_hint_classify_overrides(self):
        """测试带类型提示：classify 成功时覆盖 hint"""
        mock_ocr_result = MagicMock()
        mock_ocr_result.full_text = "合同内容..."
        self.mock_ocr.recognize = AsyncMock(return_value=mock_ocr_result)

        classify_resp = MagicMock()
        classify_resp.content = "租赁合同"  # classify 覆盖 hint
        classify_resp.model = "deepseek-chat"

        split_resp = MagicMock()
        split_resp.content = "split_resp"

        analyze_resp = MagicMock()
        analyze_resp.content = "analyze_resp"

        score_resp = MagicMock()
        score_resp.content = "score_resp"

        self.mock_llm.chat = AsyncMock(
            side_effect=[classify_resp, split_resp, analyze_resp, score_resp]
        )
        self.mock_llm.parse_json = MagicMock(
            side_effect=[
                [{"clause_number": "第一条", "content": "内容"}],
                {"risk_level": "green", "risk_type": "无", "risk_summary": "正常",
                 "plain_explanation": "正常", "legal_basis": "《合同法》", "severity_score": 1},
                {"overall_score": 80, "risk_distribution": {"red": 0, "yellow": 0, "green": 1},
                 "one_line_summary": "风险可控", "recommendation": "sign"},
            ]
        )

        with patch("server.core.agent.async_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await self.agent.analyze(
                file_path="test.pdf",
                contract_type_hint="劳动合同",
            )
            # classify 返回 "租赁合同"，覆盖了 hint "劳动合同"
            assert result.contract_type == "租赁合同"

    async def test_analyze_llm_failure_fallback_clauses_preserved(self):
        """测试 LLM 完全失败时条款保留（修复后）

        修复前：当 _analyze_clause 返回 None 时，原始条款数据被丢弃。
        修复后：失败的条款保留并标记为 green（兜底）。
        """
        mock_ocr_result = MagicMock()
        mock_ocr_result.full_text = "合同内容"
        self.mock_ocr.recognize = AsyncMock(return_value=mock_ocr_result)

        self.mock_llm.chat = AsyncMock(side_effect=Exception("LLM 不可用"))
        self.mock_llm.parse_json = MagicMock(return_value=None)

        with patch("server.core.agent.async_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await self.agent.analyze(file_path="test.pdf")
            # 修复后：兜底条款应保留，不丢失
            assert len(result.clauses) > 0, "LLM 失败时条款不应丢失"
            # 所有条款应标记为 green（兜底）
            assert result.clauses[0]["risk_level"] == "green"
            # 应有评分（基于绿色条款计算）
            assert result.overall_score > 0

    async def test_analyze_step_callback(self):
        """测试步骤回调"""
        mock_ocr_result = MagicMock()
        mock_ocr_result.full_text = ""
        self.mock_ocr.recognize = AsyncMock(return_value=mock_ocr_result)

        callback = AsyncMock()
        result = await self.agent.analyze(file_path="test.pdf", on_step=callback)

        callback.assert_called_once()

    async def test_analyze_ocr_exception(self):
        """测试 OCR 异常处理"""
        self.mock_ocr.recognize = AsyncMock(side_effect=Exception("OCR 崩溃"))

        result = await self.agent.analyze(file_path="test.pdf")
        assert result.contract_id == ""

    async def test_analyze_step6_suggest_for_red_yellow(self):
        """测试 Step 6 仅对红色/黄色条款生成建议"""
        mock_ocr_result = MagicMock()
        mock_ocr_result.full_text = "合同内容"
        self.mock_ocr.recognize = AsyncMock(return_value=mock_ocr_result)

        classify_resp = MagicMock()
        classify_resp.content = "租赁合同"

        split_resp = MagicMock()
        split_resp.content = "split_resp"

        # 两个条款分析响应
        analyze_red = MagicMock()
        analyze_red.content = "red_resp"
        analyze_green = MagicMock()
        analyze_green.content = "green_resp"

        suggest_resp = MagicMock()
        suggest_resp.content = "suggest_resp"

        score_resp = MagicMock()
        score_resp.content = "score_resp"

        self.mock_llm.chat = AsyncMock(
            side_effect=[classify_resp, split_resp, analyze_red, analyze_green, suggest_resp, score_resp]
        )

        self.mock_llm.parse_json = MagicMock(
            side_effect=[
                # Step 3 split
                [
                    {"clause_number": "第一条", "content": "高风险条款"},
                    {"clause_number": "第二条", "content": "正常条款"},
                ],
                # Step 5 analyze red
                {"risk_level": "red", "risk_type": "霸王条款", "risk_summary": "不公平",
                 "plain_explanation": "不公平", "legal_basis": "《合同法》", "severity_score": 9},
                # Step 5 analyze green
                {"risk_level": "green", "risk_type": "无", "risk_summary": "正常",
                 "plain_explanation": "正常", "legal_basis": "《合同法》", "severity_score": 1},
                # Step 6 suggest (only for red)
                {"suggested_clause": "修改后的条款", "can_negotiate": True},
                # Step 7 score
                {"overall_score": 40, "risk_distribution": {"red": 1, "yellow": 0, "green": 1},
                 "one_line_summary": "有高风险条款", "recommendation": "negotiate_first"},
            ]
        )

        with patch("server.core.agent.async_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await self.agent.analyze(file_path="test.pdf")
            assert result.overall_score == 40
            assert result.red_count == 1
            assert result.green_count == 1
            # 红色条款应有修改建议
            red_clause = [c for c in result.clauses if c.get("risk_level") == "red"]
            assert len(red_clause) == 1
            assert red_clause[0].get("suggested_clause") == "修改后的条款"
            # 绿色条款不应有修改建议
            green_clause = [c for c in result.clauses if c.get("risk_level") == "green"]
            assert len(green_clause) == 1
            assert green_clause[0].get("suggested_clause", "") == ""
