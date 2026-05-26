"""JSON report renderer."""

from __future__ import annotations

import json

from agent_guard.models import Finding
from agent_guard.scoring import RiskScore


def render_json(findings: list[Finding], score: RiskScore) -> str:
    payload = {
        "version": 1,
        "score": score.score,
        "grade": score.grade,
        "severity_counts": score.severity_counts,
        "category_counts": score.category_counts,
        "findings": [f.to_dict() for f in findings],
    }
    return json.dumps(payload, indent=2, sort_keys=True)
