"""Configuration loading for `.agent-guard.yml`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class AnalyzerConfig(BaseModel):
    enabled: bool = True
    options: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}


class AgentGuardConfig(BaseModel):
    analyzers: dict[str, AnalyzerConfig] = Field(default_factory=dict)
    fail_above: int = 60
    exclude: list[str] = Field(default_factory=list)
    include: list[str] = Field(default_factory=list)

    @classmethod
    def load(cls, path: Path | None) -> AgentGuardConfig:
        if path is None or not path.exists():
            return cls()
        data = yaml.safe_load(path.read_text()) or {}
        # Normalize: analyzers may be `name: {enabled: bool, ...rest}` where rest goes into options.
        analyzers = data.get("analyzers", {})
        normalized: dict[str, Any] = {}
        for name, cfg in analyzers.items():
            if not isinstance(cfg, dict):
                normalized[name] = AnalyzerConfig()
                continue
            enabled = cfg.pop("enabled", True)
            normalized[name] = AnalyzerConfig(enabled=enabled, options=cfg)
        data["analyzers"] = normalized
        return cls(**data)

    def analyzer_options(self, analyzer_id: str) -> dict[str, Any]:
        cfg = self.analyzers.get(analyzer_id)
        return cfg.options if cfg else {}

    def is_enabled(self, analyzer_id: str) -> bool:
        cfg = self.analyzers.get(analyzer_id)
        return cfg.enabled if cfg else True
