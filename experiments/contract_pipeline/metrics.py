"""Pure, privacy-preserving metrics for Route B experiment records."""

from __future__ import annotations

from itertools import combinations
from statistics import median, pstdev
from typing import Any


def _get(item: Any, key: str, default=None):
    return item.get(key, default) if isinstance(item, dict) else getattr(item, key, default)


def summarize_calls(records) -> dict:
    records = list(records)
    complete = [r for r in records if all(_get(r, key) is not None for key in ("input_tokens", "output_tokens", "tokens_used"))]
    latencies = sorted((_get(r, "latency_ms", 0) or 0) for r in records)
    p95_index = max(0, min(len(latencies) - 1, int(len(latencies) * 0.95))) if latencies else None
    return {
        "call_count": len(records),
        "success_count": sum(bool(_get(r, "success", False)) for r in records),
        "input_tokens": sum((_get(r, "input_tokens", 0) or 0) for r in records),
        "output_tokens": sum((_get(r, "output_tokens", 0) or 0) for r in records),
        "tokens_used": sum((_get(r, "tokens_used", 0) or 0) for r in records),
        "token_coverage": len(complete) / len(records) if records else 0.0,
        "total_latency_ms": sum(latencies),
        "median_latency_ms": median(latencies) if latencies else 0,
        "p95_latency_ms": latencies[p95_index] if p95_index is not None else 0,
    }


def estimate_cost(records, pricing) -> dict:
    required = ("currency", "input_per_million", "output_per_million")
    if not isinstance(pricing, dict) or any(pricing.get(key) in (None, "") for key in required):
        return {"cost": None, "currency": pricing.get("currency", "") if isinstance(pricing, dict) else "", "reason": "价格快照不完整"}
    records = list(records)
    if any(_get(r, key) is None for r in records for key in ("input_tokens", "output_tokens")):
        return {"cost": None, "currency": pricing["currency"], "reason": "Token 记录不完整"}
    cost = sum(
        ((_get(r, "input_tokens") or 0) * pricing["input_per_million"]
         + (_get(r, "output_tokens") or 0) * pricing["output_per_million"]) / 1_000_000
        for r in records
    )
    return {"cost": cost, "currency": pricing["currency"], "reason": None}


def risk_distribution(clauses) -> dict[str, int]:
    result = {"red": 0, "yellow": 0, "green": 0, "unknown": 0}
    for clause in clauses:
        level = _get(clause, "riskLevel", _get(clause, "risk_level", "unknown"))
        result[level if level in result else "unknown"] += 1
    return result


def pairwise_stability(runs) -> dict:
    groups = {}
    for run in runs:
        groups.setdefault((_get(run, "sample_id", ""), _get(run, "mode", "")), []).append(run)
    comparisons = []
    for group in groups.values():
        comparisons.extend(combinations(group, 2))
    agreements = []
    for left, right in comparisons:
        left_map = {_get(c, "clause_number", ""): _get(c, "risk_level", _get(c, "riskLevel", "unknown")) for c in (_get(left, "clauses", []) or [])}
        right_map = {_get(c, "clause_number", ""): _get(c, "risk_level", _get(c, "riskLevel", "unknown")) for c in (_get(right, "clauses", []) or [])}
        keys = set(left_map) | set(right_map)
        agreements.append(sum(left_map.get(key) == right_map.get(key) for key in keys) / len(keys) if keys else 1.0)
    scores = [_get(run, "overall_score") for run in runs if _get(run, "overall_score") is not None]
    clause_counts = [len(_get(run, "clauses", []) or []) for run in runs]
    return {
        "comparisons": len(comparisons),
        "risk_level_agreement": sum(agreements) / len(agreements) if agreements else 1.0,
        "clause_count_stddev": pstdev(clause_counts) if len(clause_counts) > 1 else 0.0,
        "overall_score_stddev": pstdev(scores) if len(scores) > 1 else 0.0,
    }


def structured_success_rate(runs) -> float:
    runs = list(runs)
    if not runs:
        return 0.0
    return sum(bool(_get(run, "success", False)) and _get(run, "analysis_status") == "completed" for run in runs) / len(runs)


def review_capture_rate(injected_failures) -> float:
    failures = list(injected_failures)
    if not failures:
        return 0.0
    return sum(bool(_get(item, "captured", False)) for item in failures) / len(failures)
