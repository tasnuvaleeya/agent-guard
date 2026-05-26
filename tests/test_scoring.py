from agent_guard.models import Finding, Severity
from agent_guard.scoring import score_findings


def _make(severity: Severity) -> Finding:
    return Finding(
        rule_id="x",
        severity=severity,
        file="f",
        line=1,
        message="m",
        evidence="e",
        category="dangerous",
    )


def test_empty_is_clean() -> None:
    s = score_findings([])
    assert s.score == 0
    assert s.grade == "CLEAN"


def test_severities_aggregate() -> None:
    s = score_findings([_make(Severity.CRITICAL), _make(Severity.LOW)])
    assert s.score == 42
    assert s.grade == "MEDIUM"


def test_score_capped_at_100() -> None:
    s = score_findings([_make(Severity.CRITICAL)] * 10)
    assert s.score == 100
