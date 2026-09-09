"""M1-A 固定来源评测和检索指标。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


@dataclass(frozen=True)
class SourceRef:
    """评测使用的来源标识，不包含法规正文。"""

    source_key: str
    source_ref: str


@dataclass(frozen=True)
class EvaluationCase:
    """一个固定查询和其期望来源。"""

    case_id: str
    query: str
    expected_sources: tuple[SourceRef, ...]
    k: int = 5


@dataclass(frozen=True)
class EvalRetrieval:
    """评测适配器从实际检索结果中提取的安全指标。"""

    sources: tuple[SourceRef, ...]
    duplicate_hits: int = 0
    acl_leaks: int = 0
    conflict_detected: bool = False
    degraded: bool = False


def load_eval_cases(path: str | Path) -> list[EvaluationCase]:
    """读取不包含正文的固定评测集。"""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("评测集根节点必须是数组")

    cases: list[EvaluationCase] = []
    for raw in payload:
        if not isinstance(raw, dict):
            raise ValueError("评测用例必须是对象")
        expected = raw.get("expected_sources", [])
        if not isinstance(expected, list):
            raise ValueError(f"评测用例 {raw.get('case_id')} 的 expected_sources 必须是数组")
        references = tuple(
            SourceRef(
                source_key=str(item["source_key"]),
                source_ref=str(item["source_ref"]),
            )
            for item in expected
        )
        cases.append(
            EvaluationCase(
                case_id=str(raw["case_id"]),
                query=str(raw["query"]),
                expected_sources=references,
                k=int(raw.get("k", 5)),
            )
        )
    return cases


def recall_at_k(
    expected: set[SourceRef], actual: Sequence[SourceRef], k: int
) -> float:
    """计算前 k 个结果覆盖期望来源的比例。"""
    if not expected or k <= 0:
        return 0.0
    return len(expected.intersection(actual[:k])) / len(expected)


def reciprocal_rank(
    expected: set[SourceRef], actual: Sequence[SourceRef], k: int
) -> float:
    """返回第一个期望来源在前 k 个结果中的倒数排名。"""
    if not expected or k <= 0:
        return 0.0
    for index, source in enumerate(actual[:k], start=1):
        if source in expected:
            return 1.0 / index
    return 0.0


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0


def evaluate_cases(
    cases: Sequence[EvaluationCase],
    retrieve: Callable[[EvaluationCase], EvalRetrieval],
) -> dict[str, int | float]:
    """对固定用例计算来源命中、冲突、降级和 ACL 安全指标。"""
    recall5: list[float] = []
    recall10: list[float] = []
    mrr10: list[float] = []
    duplicate_hits = 0
    acl_leaks = 0
    conflict_cases = 0
    degraded_cases = 0

    for case in cases:
        result = retrieve(case)
        expected = set(case.expected_sources)
        if expected:
            recall5.append(recall_at_k(expected, result.sources, 5))
            recall10.append(recall_at_k(expected, result.sources, 10))
            mrr10.append(reciprocal_rank(expected, result.sources, 10))
        duplicate_hits += result.duplicate_hits
        acl_leaks += result.acl_leaks
        conflict_cases += int(result.conflict_detected)
        degraded_cases += int(result.degraded)

    return {
        "case_count": len(cases),
        "recall_at_5": _mean(recall5),
        "recall_at_10": _mean(recall10),
        "mrr_at_10": _mean(mrr10),
        "duplicate_hits": duplicate_hits,
        "acl_leaks": acl_leaks,
        "conflict_cases": conflict_cases,
        "degraded_cases": degraded_cases,
    }
