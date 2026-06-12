"""Stage 3: Evaluator — 一致性检查 + 聚合评分"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field

from server.core.llm import LLMGateway
from server.core.workers.workers import ClauseRisk

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """Stage 3 聚合结果"""
    overall_score: int = 0
    risk_distribution: dict[str, int] = field(
        default_factory=lambda: {"red": 0, "yellow": 0, "green": 0}
    )
    recommendation: str = "negotiate_first"
    one_line_summary: str = ""
    needs_review: list[str] = field(default_factory=list)
    top_risks: list[str] = field(default_factory=list)


async def evaluate(
    clause_risks: list[ClauseRisk],
    llm: LLMGateway,
) -> EvaluationResult:
    """
    Stage 3: 一致性检查 + 聚合评分。

    1. 检测同一条款在不同 Worker 间的评级冲突
    2. 聚合评分
    3. 生成总结
    """

    result = EvaluationResult()

    # ── 1. 一致性检查：按 clause_id 分组，检测冲突 ──
    by_clause: dict[str, list[ClauseRisk]] = defaultdict(list)
    for r in clause_risks:
        by_clause[r.clause_id].append(r)

    needs_review: list[str] = []
    for clause_id, risks in by_clause.items():
        levels = set(r.risk_level for r in risks)
        if "red" in levels and "green" in levels:
            needs_review.append(clause_id)
            logger.warning("条款 %s 评级冲突: %s", clause_id, levels)

    # ── 2. 聚合评分 ──
    risk_list_text = "\n".join(
        f"条款 {r.clause_id}: {r.risk_level} ({r.risk_type}) - {r.issue}"
        for r in clause_risks
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

    resp = await llm.chat(messages, task="scoring")

    if resp.content:
        parsed = llm.parse_json(resp.content)
        if isinstance(parsed, dict):
            result.overall_score = parsed.get("overall_score", 50)
            result.risk_distribution = parsed.get(
                "risk_distribution", {"red": 0, "yellow": 0, "green": 0}
            )
            result.recommendation = parsed.get("recommendation", "negotiate_first")
            result.one_line_summary = parsed.get("one_line_summary", "")
            result.top_risks = parsed.get("top_risks", [])

    # ── 兜底：如果 LLM 没给出分布，从条款统计 ──
    if not any(result.risk_distribution.values()):
        for r in clause_risks:
            level = r.risk_level
            if level in result.risk_distribution:
                result.risk_distribution[level] += 1

    # 如果没有评分，根据红黄绿比例计算
    if result.overall_score == 0:
        total = sum(result.risk_distribution.values())
        if total > 0:
            result.overall_score = int(
                (result.risk_distribution["green"] * 90
                 + result.risk_distribution["yellow"] * 60
                 + result.risk_distribution["red"] * 20) / total
            )

    result.needs_review = needs_review

    logger.info(
        "Stage 3 完成: score=%d red=%d yellow=%d green=%d review=%d",
        result.overall_score,
        result.risk_distribution.get("red", 0),
        result.risk_distribution.get("yellow", 0),
        result.risk_distribution.get("green", 0),
        len(needs_review),
    )
    return result
