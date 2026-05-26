"""AST-based detection of dangerous Python call sites + cross-language regex fallbacks."""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable

from agent_guard.analyzers.base import Analyzer, Context
from agent_guard.models import FileChange, Finding, Severity

# Cross-language regex rules — fire on the added line text regardless of language.
_REGEX_RULES: list[tuple[str, Severity, re.Pattern[str], str]] = [
    ("dangerous.bind-all-interfaces", Severity.MEDIUM, re.compile(r"0\.0\.0\.0"), "Service bound to 0.0.0.0 (all interfaces)"),
    ("dangerous.chmod-777", Severity.HIGH, re.compile(r"\bchmod\s+-?\s*[0-7]*7{2,3}\b"), "World-writable chmod"),
    ("dangerous.curl-pipe-bash", Severity.HIGH, re.compile(r"curl[^\n]*\|\s*(?:ba)?sh"), "curl | sh remote execution"),
    ("dangerous.permissions-write-all", Severity.HIGH, re.compile(r"permissions:\s*write-all"), "GitHub Action granted write-all permissions"),
    ("dangerous.disable-tls-verify", Severity.HIGH, re.compile(r"verify\s*=\s*False|rejectUnauthorized\s*:\s*false|--insecure\b"), "TLS verification disabled"),
]


class DangerousPatternScanner(Analyzer):
    id = "dangerous_patterns"
    category = "dangerous"

    def analyze(self, ctx: Context) -> Iterable[Finding]:
        for change in ctx.changes:
            if change.status == "deleted":
                continue
            yield from self._regex_scan(change)
            if change.is_python:
                yield from self._python_ast_scan(change)

    def _regex_scan(self, change: FileChange) -> Iterable[Finding]:
        for line_no, content in change.added_lines:
            for rule_id, severity, pattern, message in _REGEX_RULES:
                if pattern.search(content):
                    yield Finding(
                        rule_id=rule_id,
                        severity=severity,
                        file=change.path,
                        line=line_no,
                        message=message,
                        evidence=content.strip()[:200],
                        category="dangerous",
                    )

    def _python_ast_scan(self, change: FileChange) -> Iterable[Finding]:
        source = change.full_added_content
        if not source:
            return
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return

        added_lines = {ln for ln, _ in change.added_lines}

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            line = getattr(node, "lineno", 0)
            if added_lines and line not in added_lines:
                # Only flag findings touched by this diff.
                continue

            finding = self._classify_call(node, change.path, line)
            if finding:
                yield finding

    def _classify_call(self, node: ast.Call, path: str, line: int) -> Finding | None:
        name = _dotted_name(node.func)
        if name in ("eval", "exec"):
            return Finding(
                rule_id=f"dangerous.{name}-call",
                severity=Severity.CRITICAL,
                file=path,
                line=line,
                message=f"Use of `{name}` enables arbitrary code execution",
                evidence=ast.unparse(node)[:200],
                category="dangerous",
            )
        if name == "os.system":
            return Finding(
                rule_id="dangerous.os-system",
                severity=Severity.HIGH,
                file=path,
                line=line,
                message="`os.system` invokes a shell; prefer `subprocess.run` with a list",
                evidence=ast.unparse(node)[:200],
                category="dangerous",
            )
        if name in ("subprocess.run", "subprocess.call", "subprocess.Popen", "subprocess.check_output", "subprocess.check_call"):
            for kw in node.keywords:
                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    return Finding(
                        rule_id="dangerous.subprocess-shell-true",
                        severity=Severity.HIGH,
                        file=path,
                        line=line,
                        message="subprocess called with `shell=True` — shell-injection risk",
                        evidence=ast.unparse(node)[:200],
                        category="dangerous",
                    )
        if name in ("pickle.loads", "pickle.load", "cPickle.loads", "cPickle.load"):
            return Finding(
                rule_id="dangerous.pickle-load",
                severity=Severity.HIGH,
                file=path,
                line=line,
                message="`pickle` deserialization on untrusted data enables RCE",
                evidence=ast.unparse(node)[:200],
                category="dangerous",
            )
        if name == "yaml.load":
            # Flag unless an explicit safe loader is provided.
            has_safe_loader = any(
                kw.arg == "Loader" and "Safe" in ast.unparse(kw.value)
                for kw in node.keywords
            )
            if not has_safe_loader:
                return Finding(
                    rule_id="dangerous.yaml-unsafe-load",
                    severity=Severity.HIGH,
                    file=path,
                    line=line,
                    message="`yaml.load` without `SafeLoader` permits arbitrary object construction",
                    evidence=ast.unparse(node)[:200],
                    category="dangerous",
                )
        if name in ("hashlib.md5", "hashlib.sha1"):
            return Finding(
                rule_id="dangerous.weak-hash",
                severity=Severity.LOW,
                file=path,
                line=line,
                message=f"`{name}` is cryptographically broken — prefer SHA-256",
                evidence=ast.unparse(node)[:200],
                category="dangerous",
            )
        return None


def _dotted_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""
