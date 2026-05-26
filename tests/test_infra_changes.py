from pathlib import Path

from agent_guard.analyzers import Context
from agent_guard.analyzers.infra_changes import InfraChangeDetector
from agent_guard.config import AgentGuardConfig
from agent_guard.diff import parse_diff_text
from tests.conftest import make_diff


def _ctx(tmp_path: Path, path: str) -> Context:
    return Context(
        repo_root=tmp_path,
        changes=parse_diff_text(make_diff(path, ["some content"]), repo_root=tmp_path),
        config=AgentGuardConfig(),
    )


def test_flags_workflow_change(tmp_path: Path) -> None:
    findings = list(InfraChangeDetector().analyze(_ctx(tmp_path, ".github/workflows/deploy.yml")))
    assert any(f.rule_id == "infra.workflow" for f in findings)


def test_flags_terraform_change(tmp_path: Path) -> None:
    findings = list(InfraChangeDetector().analyze(_ctx(tmp_path, "infra/network.tf")))
    assert any(f.rule_id == "infra.terraform" for f in findings)


def test_flags_env_file(tmp_path: Path) -> None:
    findings = list(InfraChangeDetector().analyze(_ctx(tmp_path, ".env.production")))
    assert any(f.rule_id == "infra.env-file" for f in findings)


def test_ignores_regular_code(tmp_path: Path) -> None:
    findings = list(InfraChangeDetector().analyze(_ctx(tmp_path, "src/app/feature.py")))
    assert findings == []
