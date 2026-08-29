from experiments.contract_pipeline.metrics import (
    estimate_cost,
    pairwise_stability,
    risk_distribution,
    review_capture_rate,
    structured_success_rate,
    summarize_calls,
)


def test_summarize_calls_reports_token_coverage_and_latency_percentiles():
    result = summarize_calls([
        {"success": True, "input_tokens": 10, "output_tokens": 5, "tokens_used": 15, "latency_ms": 10},
        {"success": False, "input_tokens": None, "output_tokens": None, "tokens_used": None, "latency_ms": 30},
    ])
    assert result["call_count"] == 2
    assert result["success_count"] == 1
    assert result["input_tokens"] == 10
    assert result["output_tokens"] == 5
    assert result["tokens_used"] == 15
    assert result["token_coverage"] == 0.5
    assert result["p95_latency_ms"] == 30


def test_estimate_cost_requires_complete_pricing_and_tokens():
    records = [{"input_tokens": 1000, "output_tokens": 500, "tokens_used": 1500}]
    assert estimate_cost(records, {"currency": "CNY", "input_per_million": 2, "output_per_million": 4}) == {
        "cost": 0.004, "currency": "CNY", "reason": None
    }
    missing = estimate_cost(records, None)
    assert missing["cost"] is None
    assert missing["reason"]


def test_risk_stability_and_review_metrics_are_explicit():
    clauses = [{"riskLevel": "red"}, {"risk_level": "unknown"}, {"riskLevel": "green"}]
    assert risk_distribution(clauses) == {"red": 1, "yellow": 0, "green": 1, "unknown": 1}
    runs = [
        {"sample_id": "s1", "mode": "parallel", "overall_score": 80, "clauses": [{"clause_number": "1", "risk_level": "red"}]},
        {"sample_id": "s1", "mode": "parallel", "overall_score": 82, "clauses": [{"clause_number": "1", "risk_level": "red"}]},
    ]
    stability = pairwise_stability(runs)
    assert stability["comparisons"] == 1
    assert stability["risk_level_agreement"] == 1.0
    assert structured_success_rate([{"success": True, "analysis_status": "completed"}, {"success": False}]) == 0.5
    assert review_capture_rate([{"captured": True}, {"captured": False}]) == 0.5
