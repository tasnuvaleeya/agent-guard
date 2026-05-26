"""Render a Markdown report suitable for a sticky PR comment."""

from __future__ import annotations

from collections import defaultdict

from agent_guard.models import Finding, Severity
from agent_guard.scoring import RiskScore

STICKY_MARKER = "<!-- agent-guard -->"

_SEVERITY_EMOJI = {
    Severity.CRITICAL: "🛑",
    Severity.HIGH: "⚠️",
    Severity.MEDIUM: "🟡",
    Severity.LOW: "ℹ️",
}
_GRADE_BADGE = {
    "CRITICAL": "🛑 CRITICAL",
    "HIGH": "⚠️ HIGH",
    "MEDIUM": "🟡 MEDIUM",
    "LOW": "ℹ️ LOW",
    "CLEAN": "✅ CLEAN",
}


def render_markdown(findings: list[Finding], score: RiskScore) -> str:
    lines: list[str] = [STICKY_MARKER, "## agent-guard"]
    lines.append(f"**Risk score:** `{score.score}/100` — {_GRADE_BADGE[score.grade]}")
    lines.append("")

    counts = score.severity_counts
    lines.append(
        f"| 🛑 Critical | ⚠️ High | 🟡 Medium | ℹ️ Low |\n"
        f"|---|---|---|---|\n"
        f"| {counts.get('critical', 0)} | {counts.get('high', 0)} | {counts.get('medium', 0)} | {counts.get('low', 0)} |"
    )
    lines.append("")

    if not findings:
        lines.append("_No findings — diff looks clean._")
        return "\n".join(lines)

    grouped: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        grouped[f.category].append(f)

    category_order = ["secret", "hallucination", "dangerous", "tests", "infra", "semantic", "policy"]
    for category in category_order:
        items = grouped.get(category)
        if not items:
            continue
        lines.append(f"### {_category_title(category)} ({len(items)})")
        items_sorted = sorted(items, key=lambda i: (-i.severity.weight, i.file, i.line))
        for f in items_sorted:
            loc = f"`{f.file}`" if f.line == 0 else f"`{f.file}:{f.line}`"
            emoji = _SEVERITY_EMOJI[f.severity]
            lines.append(f"- {emoji} **{f.rule_id}** — {loc}")
            lines.append(f"  - {f.message}")
            if f.evidence:
                lines.append(f"  - <details><summary>evidence</summary><pre>{_escape(f.evidence)}</pre></details>")
        lines.append("")

    lines.append("---")
    lines.append("<sub>agent-guard scans diffs for AI-generated risk patterns. Configure via `.agent-guard.yml`.</sub>")
    return "\n".join(lines)


def _category_title(category: str) -> str:
    return {
        "secret": "🔐 Secrets",
        "hallucination": "🤖 Hallucinated imports",
        "dangerous": "💣 Dangerous patterns",
        "tests": "🧪 Missing tests",
        "infra": "🏗️ Infrastructure changes",
        "semantic": "🧠 Semantic smells",
        "policy": "📜 Policy violations",
    }.get(category, category.title())


def _escape(s: str) -> str:
    return s.replace("<", "&lt;").replace(">", "&gt;")
