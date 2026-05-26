"""Aggregates findings into a 0-100 risk score."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from agent_guard.models import Finding, Severity


@dataclass
class RiskScore:
    score: int
    severity_counts: dict[str, int]
    category_counts: dict[str, int]

    @property
    def grade(self) -> str:
        if self.score >= 80:
            return "CRITICAL"
        if self.score >= 60:
            return "HIGH"
        if self.score >= 30:
            return "MEDIUM"
        if self.score > 0:
            return "LOW"
        return "CLEAN"


def score_findings(findings: list[Finding]) -> RiskScore:
    raw = sum(f.severity.weight for f in findings)
    score = min(raw, 100)
    sev_counts: Counter[str] = Counter(f.severity.value for f in findings)
    cat_counts: Counter[str] = Counter(f.category for f in findings)
    # Ensure stable key set for downstream rendering.
    for s in Severity:
        sev_counts.setdefault(s.value, 0)
    return RiskScore(
        score=score,
        severity_counts=dict(sev_counts),
        category_counts=dict(cat_counts),
    )
