"""Shared data types used across analyzers and reporters."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def weight(self) -> int:
        return {"low": 2, "medium": 8, "high": 20, "critical": 40}[self.value]


Category = Literal["secret", "hallucination", "dangerous", "tests", "infra", "semantic", "policy"]
FileStatus = Literal["added", "modified", "deleted", "renamed"]


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: Severity
    file: str
    line: int
    message: str
    evidence: str
    category: Category
    suggested_fix: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "file": self.file,
            "line": self.line,
            "message": self.message,
            "evidence": self.evidence,
            "category": self.category,
            "suggested_fix": self.suggested_fix,
            "metadata": self.metadata,
        }


@dataclass
class FileChange:
    path: str
    status: FileStatus
    added_lines: list[tuple[int, str]] = field(default_factory=list)
    removed_lines: list[tuple[int, str]] = field(default_factory=list)
    full_added_content: str | None = None

    @property
    def is_python(self) -> bool:
        return self.path.endswith(".py")

    def added_text(self) -> str:
        return "\n".join(content for _, content in self.added_lines)
