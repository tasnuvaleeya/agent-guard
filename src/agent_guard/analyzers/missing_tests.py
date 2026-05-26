"""Heuristic: flag PRs that add source code without touching tests."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from agent_guard.analyzers.base import Analyzer, Context
from agent_guard.models import FileChange, Finding, Severity

_TEST_PATH_RE = re.compile(r"(^|/)(tests?|__tests__|spec)(/|$)|(^|/)test_[^/]*\.(py|ts|tsx|js|jsx|go|rs|java)$|\.test\.(ts|tsx|js|jsx)$|\.spec\.(ts|tsx|js|jsx)$|_test\.go$")
_SOURCE_EXT = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java"}
_EXCLUDE_DIRS = (
    "docs/", "doc/", "examples/", "example/", "scripts/", "tools/",
    "vendor/", "third_party/", ".github/", "node_modules/",
)


class MissingTestsAnalyzer(Analyzer):
    id = "missing_tests"
    category = "tests"

    min_added_lines: int = 30
    min_source_files: int = 1

    def configure(self, options: dict[str, Any]) -> None:
        self.min_added_lines = int(options.get("min_added_lines", self.min_added_lines))
        self.min_source_files = int(options.get("min_source_files", self.min_source_files))

    def analyze(self, ctx: Context) -> Iterable[Finding]:
        source_files: list[FileChange] = []
        test_files: list[FileChange] = []
        added_lines = 0

        for change in ctx.changes:
            if change.status == "deleted":
                continue
            if _TEST_PATH_RE.search(change.path):
                test_files.append(change)
                continue
            if not self._looks_like_source(change.path):
                continue
            source_files.append(change)
            added_lines += len(change.added_lines)

        if not source_files:
            return
        if test_files:
            return
        if added_lines < self.min_added_lines:
            return
        if len(source_files) < self.min_source_files:
            return

        # File-level finding on the largest source change.
        primary = max(source_files, key=lambda c: len(c.added_lines))
        yield Finding(
            rule_id="tests.missing",
            severity=Severity.MEDIUM,
            file=primary.path,
            line=0,
            message=(
                f"{len(source_files)} source file(s) changed (+{added_lines} lines) but no tests were added or modified. "
                "AI-generated code is especially likely to skip tests."
            ),
            evidence=", ".join(c.path for c in source_files[:5]) + (" …" if len(source_files) > 5 else ""),
            category="tests",
            metadata={"added_lines": added_lines, "source_files": [c.path for c in source_files]},
        )

    @staticmethod
    def _looks_like_source(path: str) -> bool:
        if any(path.startswith(d) for d in _EXCLUDE_DIRS):
            return False
        return any(path.endswith(ext) for ext in _SOURCE_EXT)
