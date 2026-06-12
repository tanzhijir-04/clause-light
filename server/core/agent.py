"""Agent Harness — 7 步合同分析流程"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from server.config import TYPE_EN_MAP
from server.core.knowledge import KnowledgeEngine
from server.core.llm import LLMGateway, get_llm_gateway
from server.core.ocr import OCREngine, get_ocr_engine
from server.core.prompts.analyze import analyze_prompt
from server.core.prompts.classify import classify_prompt
from server.core.prompts.score import score_prompt
from server.core.prompts.split import split_prompt
from server.core.prompts.suggest import suggest_prompt
from server.models.database import (
    Analysis,
    ClauseAnalysis,
    Contract,
    async_session_factory,
)

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """分析结果"""

    contract_id: str = ""
    contract_type: str = ""
    contract_type_en: str = "other"
    overall_score: int = 0
    recommendation: str = "negotiate_first"
    summary: str = ""
    model_used: str = ""
    clauses: list[dict] = field(default_factory=list)
    red_count: int = 0
    yellow_count: int = 0
    green_count: int = 0


class ContractAgent:
    """合同分析 Agent — 7 步流程"""

    def __init__(
        self,
        llm: LLMGateway | None = None,
        ocr: OCREngine | None = None,
    ) -> None:
        self.llm = llm or get_llm_gateway()
        self.ocr = ocr or get_ocr_engine()

    async def analyze(
        self,
        file_path: str,
        contract_type_hint: str | None = None,
        on_step: Callable | None = None,
    ) -> AnalysisResult:
        """
        完整的 7 步分析流程。

        Step 1: OCR 识别
        Step 2: 合同分类（LLM）
        Step 3: 条款拆解（LLM）
        Step 4: 知识库检索
        Step 5: 逐条风险分析（LLM，并行）
        Step 6: 修改建议生成（LLM）
        Step 7: 综合评分（LLM）
        """

        async def _notify(step: int, total: int, message: str) -> None:
            if on_step:
                try:
                    await on_step(step, total, message)
                except Exception:
                    pass

        result = AnalysisResult()
        contract_id = uuid.uuid4().hex

        # ── Step 1: OCR 识别 ──
        await _notify(1, 7, "正在识别文字...")
        logger.info("Step 1/7: OCR 识别")
        try:
            ocr_result = await self._retry(lambda: self.ocr.recognize(file_path), "OCR 识别")
            if not ocr_result or not ocr_result.full_text.strip():
                logger.error("OCR 识别结果为空")
                return result
            full_text = ocr_result.full_text
        except Exception as e:
            logger.error("Step 1 失败: %s", e)
            return result

        # ── Step 2: 合同分类 ──
        await _notify(2, 7, "正在分类合同...")
        logger.info("Step 2/7: 合同分类")
        contract_type = contract_type_hint or "其他"
        try:
            resp = await self.llm.chat(
                classify_prompt(full_text), task="classification"
            )
            if resp.content:
                # 清理 LLM 输出（去掉引号、换行等）
                parsed_type = resp.content.strip().strip('"').strip("'").strip()
                if parsed_type:
                    contract_type = parsed_type
                result.model_used = resp.model
        except Exception as e:
            logger.warning("Step 2 使用默认类型: %s", e)

        result.contract_type = contract_type
        result.contract_type_en = TYPE_EN_MAP.get(contract_type, "other")

        # ── Step 3: 条款拆解 ──
        await _notify(3, 7, "正在拆解条款...")
        logger.info("Step 3/7: 条款拆解")
        clauses: list[dict] = []
        try:
            resp = await self.llm.chat(
                split_prompt(full_text, contract_type), task="analysis"
            )
            if resp.content:
                parsed = self.llm.parse_json(resp.content)
                if isinstance(parsed, list):
                    clauses = parsed
                elif isinstance(parsed, dict) and "clauses" in parsed:
                    clauses = parsed["clauses"]
        except Exception as e:
            logger.warning("Step 3 失败: %s", e)

        if not clauses:
            # 兜底：将全文作为一个条款
            clauses = [{"clause_number": "第一条", "title": "全文", "content": full_text[:2000]}]

        # ── Step 4: 知识库检索 ──
        await _notify(4, 7, "正在检索知识库...")
        logger.info("Step 4/7: 知识库检索")
        kb_rules: list[str] = []
        try:
            async with async_session_factory() as db:
                knowledge = KnowledgeEngine(db)
                kb_rules = await knowledge.search(full_text[:500], contract_type)
        except Exception as e:
            logger.warning("Step 4 知识库检索失败: %s", e)

        # ── Step 5: 逐条风险分析（并行） ──
        await _notify(5, 7, f"正在分析 {len(clauses)} 条条款...")
        logger.info("Step 5/7: 逐条风险分析 (%d 条)", len(clauses))

        analysis_tasks = [
            self._analyze_clause(clause, contract_type, full_text[:1000], kb_rules)
            for clause in clauses
        ]
        clause_results = await asyncio.gather(*analysis_tasks, return_exceptions=True)

        analyzed_clauses: list[dict] = []
        for i, res in enumerate(clause_results):
            if isinstance(res, Exception):
                logger.warning("条款 %d 分析失败: %s", i, res)
                # 兜底：未分析的条款标为绿色
                analyzed_clauses.append({
                    **clauses[i],
                    "risk_level": "green",
                    "risk_type": "未分析",
                    "risk_summary": "分析失败",
                    "plain_explanation": "",
                    "severity_score": 1,
                })
            elif res is not None:
                analyzed_clauses.append({**clauses[i], **res})
            else:
                # _analyze_clause 返回 None，保留原始条款并标记为未分析
                analyzed_clauses.append({
                    **clauses[i],
                    "risk_level": "green",
                    "risk_type": "未分析",
                    "risk_summary": "分析结果为空",
                    "plain_explanation": "",
                    "severity_score": 1,
                })

        result.clauses = analyzed_clauses

        # ── Step 6: 修改建议 ──
        await _notify(6, 7, "正在生成修改建议...")
        logger.info("Step 6/7: 修改建议生成")
        for clause in analyzed_clauses:
            if clause.get("risk_level") in ("red", "yellow"):
                try:
                    resp = await self.llm.chat(
                        suggest_prompt(
                            clause.get("content", ""),
                            clause.get("risk_type", ""),
                        ),
                        task="explanation",
                    )
                    if resp.content:
                        parsed = self.llm.parse_json(resp.content)
                        if isinstance(parsed, dict):
                            clause["suggested_clause"] = parsed.get("suggested_clause", "")
                            clause["can_negotiate"] = parsed.get("can_negotiate", False)
                except Exception as e:
                    logger.warning("Step 6 建议生成失败: %s", e)

        # ── Step 7: 综合评分 ──
        await _notify(7, 7, "正在综合评分...")
        logger.info("Step 7/7: 综合评分")
        try:
            resp = await self.llm.chat(
                score_prompt(analyzed_clauses), task="scoring"
            )
            if resp.content:
                parsed = self.llm.parse_json(resp.content)
                if isinstance(parsed, dict):
                    result.overall_score = parsed.get("overall_score", 50)
                    result.summary = parsed.get("one_line_summary", "")
                    result.recommendation = parsed.get("recommendation", "negotiate_first")
                    dist = parsed.get("risk_distribution", {})
                    result.red_count = dist.get("red", 0)
                    result.yellow_count = dist.get("yellow", 0)
                    result.green_count = dist.get("green", 0)
        except Exception as e:
            logger.warning("Step 7 评分失败: %s", e)

        # 如果 LLM 没有给出分布，从条款统计
        if not result.red_count and not result.yellow_count and not result.green_count:
            for c in analyzed_clauses:
                level = c.get("risk_level", "green")
                if level == "red":
                    result.red_count += 1
                elif level == "yellow":
                    result.yellow_count += 1
                else:
                    result.green_count += 1

        # 如果没有评分，根据红黄绿比例计算
        if result.overall_score == 0:
            total = result.red_count + result.yellow_count + result.green_count
            if total > 0:
                result.overall_score = int(
                    (result.green_count * 90 + result.yellow_count * 60 + result.red_count * 20) / total
                )

        result.contract_id = contract_id
        logger.info(
            "分析完成: score=%d red=%d yellow=%d green=%d",
            result.overall_score,
            result.red_count,
            result.yellow_count,
            result.green_count,
        )
        return result

    async def _analyze_clause(
        self,
        clause: dict,
        contract_type: str,
        context: str,
        kb_rules: list[str],
    ) -> dict | None:
        """分析单条条款的风险"""
        try:
            resp = await self.llm.chat(
                analyze_prompt(
                    clause.get("content", ""),
                    contract_type,
                    context,
                    kb_rules,
                ),
                task="analysis",
            )
            if resp.content:
                parsed = self.llm.parse_json(resp.content)
                if isinstance(parsed, dict):
                    return parsed
        except Exception as e:
            logger.warning("条款分析失败: %s", e)
        return None

    async def _retry(self, fn, step_name: str, max_retries: int = 2):
        """带重试的异步调用"""
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                return await fn()
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    logger.warning("%s 重试 %d/%d: %s", step_name, attempt + 1, max_retries, e)
                    await asyncio.sleep(1.0 * (attempt + 1))
        raise last_error  # type: ignore
