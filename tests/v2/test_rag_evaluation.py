from __future__ import annotations

from pathlib import Path

from server.modules.rag.evaluation import (
    EvalRetrieval,
    SourceRef,
    evaluate_cases,
    load_eval_cases,
    recall_at_k,
    reciprocal_rank,
)


def test_recall_and_reciprocal_rank_use_expected_sources():
    expected = {
        SourceRef("law.json", "第一条"),
        SourceRef("law.json", "第二条"),
    }
    actual = [
        SourceRef("other.json", "第一条"),
        SourceRef("law.json", "第二条"),
        SourceRef("law.json", "第一条"),
    ]

    assert recall_at_k(expected, actual, 2) == 0.5
    assert reciprocal_rank(expected, actual, 3) == 0.5


def test_fixed_eval_cases_have_expected_source_shape():
    cases = load_eval_cases(Path("tests/fixtures/rag/eval_cases.json"))

    assert len(cases) == 8
    assert cases[0].expected_sources[0].source_ref == "第四百六十九条"
    assert cases[-1].expected_sources == ()


def test_evaluate_cases_is_deterministic_and_reports_safety_metrics():
    cases = load_eval_cases(Path("tests/fixtures/rag/eval_cases.json"))[:2]
    source = SourceRef("shared/laws/civil_code.json", "第四百六十九条")

    def retrieve(case):
        return EvalRetrieval(
            sources=(source,),
            duplicate_hits=1,
            acl_leaks=0,
            conflict_detected=case.case_id.endswith("content-001"),
            degraded=True,
        )

    first = evaluate_cases(cases, retrieve)
    second = evaluate_cases(cases, retrieve)

    assert first == second
    assert first["case_count"] == 2
    assert first["recall_at_5"] == 0.5
    assert first["mrr_at_10"] == 0.5
    assert first["duplicate_hits"] == 2
    assert first["acl_leaks"] == 0
    assert first["conflict_cases"] == 1
    assert first["degraded_cases"] == 2
