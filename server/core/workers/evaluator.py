"""Stage 3: Evaluator — 一致性检查 + 聚合评分"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field

from server.core.llm import LLMGateway
from server.core.schemas.llm_outputs import EvaluationSchema
from server.core.workers.workers import ClauseRisk

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """Stage 3 聚合结果"""
    overall_score: int | None = None
    risk_distribution: dict[str, int] = field(
        default_factory=lambda: {"red": 0, "yellow": 0, "green": 0, "unknown": 0}
    )
    recommendation: str = "negotiate_first"
    one_line_summary: str = ""
    needs_review: list[str] = field(default_factory=list)
    top_risks: list[str] = field(default_factory=list)


async def evaluate(
    clause_risks: list[ClauseRisk],
    llm: LLMGateway,
) -> EvaluationResult:
    """Filter unreliable Worker results, then aggregate reliable ratings."""
    valid_risks = [
        r
        for r in clause_risks
        if r.analysis_status in {"completed", "resolved"}
        and r.risk_level in {"red", "yellow", "green"}
    ]
    failed_risks = [r for r in clause_risks if r not in valid_risks]
    failed_clause_ids = {r.clause_id for r in failed_risks if r.clause_id}
    failed_count = len(failed_risks)

    if not valid_risks:
        return EvaluationResult(
            overall_score=None,
            risk_distribution={
                "red": 0,
                "yellow": 0,
                "green": 0,
                "unknown": failed_count,
            },
            recommendation="manual_review",
            one_line_summary="系统未形成可用评级，请人工复核",
            needs_review=sorted(failed_clause_ids),
        )

    result = EvaluationResult()

    # ── 1. 一致性检查：仅在可靠结果中检测冲突 ──
    by_clause: dict[str, list[ClauseRisk]] = defaultdict(list)
    for r in valid_risks:
        by_clause[r.clause_id].append(r)

    needs_review: list[str] = []
    for clause_id, risks in by_clause.items():
        levels = set(r.risk_level for r in risks)
        if "red" in levels and "green" in levels:
            needs_review.append(clause_id)
            logger.warning("条款 %s 评级冲突: %s", clause_id, levels)

    # ── 2. 聚合评分：提示词不携带失败或 unknown 结果 ──
    risk_list_text = "\n".join(
        f"条款 {r.clause_id}: {r.risk_level} ({r.risk_type}) - {r.issue}"
        for r in valid_risks
    )

    system_prompt = (
        "你是合同风险评估的聚合专家。基于各维度 Worker 的分析结果，给出综合评分。\n\n"
        "## 评分标准\n"
        "- 0-30: 高风险，建议不签或大幅修改后再签\n"
        "- 31-60: 中等风险，建议重点协商后再签\n"
        "- 61-80: 低风险，可签但建议微调\n"
        "- 81-100: 风险很低，可直接签署\n\n"
        "## 输出格式\n"
        "只返回 JSON 对象，不要包含任何其他文字或 markdown 格式：\n"
        "{\n"
        '  "overall_score": 0-100,\n'
        '  "risk_distribution": {"red": N, "yellow": N, "green": N},\n'
        '  "top_risks": ["最危险的3个风险（一句话）"],\n'
        '  "one_line_summary": "一句话总结",\n'
        '  "recommendation": "sign / negotiate_first / reject"\n'
        "}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"分析结果：\n{risk_list_text}"},
    ]

    resp = await llm.chat_structured(
        messages, schema=EvaluationSchema, task="scoring"
    )

    if isinstance(resp.parsed, EvaluationSchema):
        parsed = resp.parsed.model_dump()
        result.overall_score = parsed.get("overall_score", 50)
        result.risk_distribution = parsed.get(
            "risk_distribution", {"red": 0, "yellow": 0, "green": 0}
        )
        result.recommendation = parsed.get("recommendation", "negotiate_first")
        result.one_line_summary = parsed.get("one_line_summary", "")
        result.top_risks = parsed.get("top_risks", [])
    elif resp.content:
        parsed = llm.parse_json(resp.content)
        if isinstance(parsed, dict):
            result.overall_score = parsed.get("overall_score", 50)
            result.risk_distribution = parsed.get(
                "risk_distribution", {"red": 0, "yellow": 0, "green": 0}
            )
            result.recommendation = parsed.get("recommendation", "negotiate_first")
            result.one_line_summary = parsed.get("one_line_summary", "")
            result.top_risks = parsed.get("top_risks", [])

    # ── 兜底：如果 LLM 没给出分布，从可靠条款统计 ──
    if not any(result.risk_distribution.get(level, 0) for level in ("red", "yellow", "green")):
        for r in valid_risks:
            result.risk_distribution[r.risk_level] += 1

    result.risk_distribution.setdefault("unknown", 0)
    result.risk_distribution["unknown"] = failed_count

    # 如果没有评分，根据红黄绿比例计算；unknown 不进入分母和 green_count。
    if result.overall_score is None:
        total = sum(
            result.risk_distribution.get(level, 0)
            for level in ("red", "yellow", "green")
        )
        if total > 0:
            result.overall_score = int(
                (
                    result.risk_distribution.get("green", 0) * 90
                    + result.risk_distribution.get("yellow", 0) * 60
                    + result.risk_distribution.get("red", 0) * 20
                )
                / total
            )

    result.needs_review = sorted(set(needs_review) | failed_clause_ids)

    logger.info(
        "Stage 3 完成: score=%s red=%d yellow=%d green=%d unknown=%d review=%d",
        result.overall_score,
        result.risk_distribution.get("red", 0),
        result.risk_distribution.get("yellow", 0),
        result.risk_distribution.get("green", 0),
        result.risk_distribution.get("unknown", 0),
        len(result.needs_review),
    )
    return result
