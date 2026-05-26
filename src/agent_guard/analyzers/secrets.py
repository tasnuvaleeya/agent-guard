"""Secret detection: regex patterns + Shannon-entropy gate."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable

from agent_guard.analyzers.base import Analyzer, Context
from agent_guard.models import Finding, Severity

# High-precision patterns. Each entry: (rule_suffix, severity, pattern, label)
_PATTERNS: list[tuple[str, Severity, re.Pattern[str], str]] = [
    ("aws-access-key", Severity.CRITICAL, re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"), "AWS access key"),
    ("aws-secret-key", Severity.CRITICAL, re.compile(r"(?i)aws_secret_access_key\s*[=:]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?"), "AWS secret key"),
    ("github-pat", Severity.CRITICAL, re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"), "GitHub personal access token"),
    ("github-app", Severity.CRITICAL, re.compile(r"\b(github_pat_[A-Za-z0-9_]{82})\b"), "GitHub fine-grained token"),
    ("slack-token", Severity.HIGH, re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"), "Slack token"),
    ("slack-webhook", Severity.HIGH, re.compile(r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+"), "Slack webhook"),
    ("openai-key", Severity.CRITICAL, re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{20,}\b"), "OpenAI API key"),
    ("anthropic-key", Severity.CRITICAL, re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b"), "Anthropic API key"),
    ("google-api-key", Severity.HIGH, re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "Google API key"),
    ("gcp-service-account", Severity.CRITICAL, re.compile(r'"type"\s*:\s*"service_account"'), "GCP service account JSON"),
    ("stripe-key", Severity.CRITICAL, re.compile(r"\b(sk|rk)_(live|test)_[A-Za-z0-9]{24,}\b"), "Stripe API key"),
    ("private-key-block", Severity.CRITICAL, re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"), "Private key block"),
    ("jwt", Severity.MEDIUM, re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"), "JWT token"),
    ("npm-token", Severity.HIGH, re.compile(r"\bnpm_[A-Za-z0-9]{36}\b"), "npm token"),
    ("postgres-url", Severity.HIGH, re.compile(r"postgres(?:ql)?://[^:]+:[^@\s]+@[^\s/]+"), "Postgres URL with password"),
]

# Generic high-entropy fallback (only fires in .env / config-like files).
_ASSIGNMENT = re.compile(r"""(?P<key>[A-Z0-9_]{3,})\s*[=:]\s*['"]?(?P<val>[A-Za-z0-9/+=_\-]{20,})['"]?""")
_ENV_FILE_RE = re.compile(r"(^|/)\.env(\..+)?$|/secrets?(/|\.)", re.IGNORECASE)
_ENTROPY_THRESHOLD = 4.0


def shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = Counter(s)
    length = len(s)
    return -sum((c / length) * math.log2(c / length) for c in counts.values())


def _redact(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "…" + "*" * 4


class SecretScanner(Analyzer):
    id = "secrets"
    category = "secret"

    def analyze(self, ctx: Context) -> Iterable[Finding]:
        for change in ctx.changes:
            if change.status == "deleted":
                continue
            for line_no, content in change.added_lines:
                yield from self._scan_line(change.path, line_no, content)

    def _scan_line(self, path: str, line_no: int, content: str) -> Iterable[Finding]:
        for suffix, severity, pattern, label in _PATTERNS:
            match = pattern.search(content)
            if not match:
                continue
            evidence = match.group(0)
            yield Finding(
                rule_id=f"secrets.{suffix}",
                severity=severity,
                file=path,
                line=line_no,
                message=f"Possible {label} committed to repo",
                evidence=_redact(evidence),
                category="secret",
            )

        if _ENV_FILE_RE.search(path):
            m = _ASSIGNMENT.search(content)
            already_matched = any(p.search(content) for _, _, p, _ in _PATTERNS)
            if (
                m
                and not already_matched
                and shannon_entropy(m.group("val")) >= _ENTROPY_THRESHOLD
            ):
                yield Finding(
                    rule_id="secrets.high-entropy-env",
                    severity=Severity.HIGH,
                    file=path,
                    line=line_no,
                    message=f"High-entropy value assigned to `{m.group('key')}` in environment file",
                    evidence=f"{m.group('key')}={_redact(m.group('val'))}",
                    category="secret",
                )
