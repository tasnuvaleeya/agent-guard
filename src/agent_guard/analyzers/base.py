"""Analyzer ABC and execution Context."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_guard.config import AgentGuardConfig
from agent_guard.models import FileChange, Finding


@dataclass
class Context:
    repo_root: Path
    changes: list[FileChange]
    config: AgentGuardConfig
    cache: dict[str, Any] = field(default_factory=dict)


class Analyzer(ABC):
    """Base class for all analyzers.

    Subclasses must declare a stable `id` and `category`, and implement
    `analyze(ctx)` to yield `Finding` objects.
    """

    id: str = ""
    category: str = ""
    languages: tuple[str, ...] = ("*",)

    def configure(self, options: dict[str, Any]) -> None:
        """Override to consume per-analyzer YAML options."""
        return None

    @abstractmethod
    def analyze(self, ctx: Context) -> Iterable[Finding]: ...
