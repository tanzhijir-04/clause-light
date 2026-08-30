"""合同总体风险显示规则。"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable


def summarize_risk(
    levels: Iterable[object],
    analysis_status: str = "pending",
    needs_review: bool = False,
) -> dict[str, object]:
    """根据条款风险与分析状态生成统一的总体风险摘要。"""
    allowed = {"red", "yellow", "green", "unknown"}
    counts = Counter(level if level in allowed else "unknown" for level in levels)
    incomplete = analysis_status != "completed" or not sum(counts.values())
    review = bool(needs_review or incomplete or counts["unknown"])

    if counts["red"]:
        level = "red"
    elif counts["yellow"]:
        level = "yellow"
    elif review:
        level = "unknown"
    else:
        level = "green"

    return {
        "riskLevel": level,
        "redCount": counts["red"],
        "yellowCount": counts["yellow"],
        "greenCount": counts["green"],
        "unknownCount": counts["unknown"],
        "needsReview": review,
    }
