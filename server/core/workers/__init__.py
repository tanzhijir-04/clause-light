"""Workers — 三段式 Pipeline 的各阶段实现"""

from server.core.workers.evaluator import EvaluationResult, evaluate
from server.core.workers.parser import (
    CLAUSE_TYPES,
    ClauseItem,
    ParseResult,
    parse_contract,
)
from server.core.workers.workers import (
    ClauseRisk,
    WORKER_DIMENSIONS,
    analyze_dimension,
)

__all__ = [
    # Stage 1
    "CLAUSE_TYPES",
    "ClauseItem",
    "ParseResult",
    "parse_contract",
    # Stage 2
    "ClauseRisk",
    "WORKER_DIMENSIONS",
    "analyze_dimension",
    # Stage 3
    "EvaluationResult",
    "evaluate",
]
