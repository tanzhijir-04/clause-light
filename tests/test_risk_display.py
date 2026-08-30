import pytest

from server.core.risk_display import summarize_risk


@pytest.mark.parametrize(
    "levels,status,review,expected",
    [
        ([], "pending", False, "unknown"),
        ([], "failed", True, "unknown"),
        (["unknown"], "partial", True, "unknown"),
        (["green"], "partial", True, "unknown"),
        (["green"], "completed", False, "green"),
        (["yellow", "unknown"], "partial", True, "yellow"),
        (["red", "unknown"], "partial", True, "red"),
        ([None], "completed", False, "unknown"),
    ],
)
def test_green_requires_completed_known_results(levels, status, review, expected):
    result = summarize_risk(levels, status, review)

    assert result["riskLevel"] == expected
    if expected == "unknown":
        assert result["needsReview"] is True
