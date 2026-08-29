from experiments.contract_pipeline.report import render_report


def test_report_is_deterministic_and_states_accuracy_boundary():
    records = [
        {
            "sample_id": "s1", "independent_group": "g1", "mode": "single_pass",
            "success": True, "analysis_status": "completed", "elapsed_ms": 10,
            "overall_score": 80, "clauses": [{"clause_number": "1", "risk_level": "green"}],
            "review_reasons": {}, "estimated_cost": None, "cost_currency": "",
            "call_records": [{"success": True, "input_tokens": None, "output_tokens": None, "tokens_used": None, "latency_ms": 10, "structured_via": "chat"}],
        }
    ]
    first = render_report(records, raw_sha256="abc", commit="def")
    second = render_report(records, raw_sha256="abc", commit="def")
    assert first == second
    assert "不可计算" in first
    assert "未建立专家标注，不评价法律判断正确性" in first
