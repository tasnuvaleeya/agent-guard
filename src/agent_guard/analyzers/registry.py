"""Built-in analyzer registry."""

from __future__ import annotations

from agent_guard.analyzers.base import Analyzer
from agent_guard.analyzers.dangerous_patterns import DangerousPatternScanner
from agent_guard.analyzers.hallucinated_imports import HallucinatedImportScanner
from agent_guard.analyzers.infra_changes import InfraChangeDetector
from agent_guard.analyzers.missing_tests import MissingTestsAnalyzer
from agent_guard.analyzers.secrets import SecretScanner
from agent_guard.config import AgentGuardConfig


def default_registry() -> list[type[Analyzer]]:
    return [
        SecretScanner,
        HallucinatedImportScanner,
        DangerousPatternScanner,
        MissingTestsAnalyzer,
        InfraChangeDetector,
    ]


def get_analyzers(config: AgentGuardConfig) -> list[Analyzer]:
    instances: list[Analyzer] = []
    for cls in default_registry():
        if not config.is_enabled(cls.id):
            continue
        instance = cls()
        instance.configure(config.analyzer_options(cls.id))
        instances.append(instance)
    return instances
