from pathlib import Path

from agent_guard.analyzers import Context
from agent_guard.analyzers.hallucinated_imports import HallucinatedImportScanner
from agent_guard.config import AgentGuardConfig
from agent_guard.diff import parse_diff_text
from tests.conftest import make_diff


def _ctx(tmp_path: Path, diff_text: str) -> Context:
    return Context(
        repo_root=tmp_path,
        changes=parse_diff_text(diff_text, repo_root=tmp_path),
        config=AgentGuardConfig(),
    )


def test_flags_unknown_third_party_import(tmp_path: Path) -> None:
    # No requirements.txt, no pyproject.toml → unknown imports are flagged.
    diff = make_diff("app.py", ["from totally_made_up_pkg import sparkle", "print('hi')"])
    findings = list(HallucinatedImportScanner().analyze(_ctx(tmp_path, diff)))
    assert any(f.metadata.get("module") == "totally_made_up_pkg" for f in findings)


def test_does_not_flag_stdlib(tmp_path: Path) -> None:
    diff = make_diff("app.py", ["import os", "import json"])
    findings = list(HallucinatedImportScanner().analyze(_ctx(tmp_path, diff)))
    assert findings == []


def test_does_not_flag_declared_dependency(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("requests==2.31.0\n")
    diff = make_diff("app.py", ["import requests"])
    findings = list(HallucinatedImportScanner().analyze(_ctx(tmp_path, diff)))
    assert findings == []


def test_resolves_alias_pyyaml_for_yaml_import(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("pyyaml>=6\n")
    diff = make_diff("app.py", ["import yaml"])
    findings = list(HallucinatedImportScanner().analyze(_ctx(tmp_path, diff)))
    assert findings == []
