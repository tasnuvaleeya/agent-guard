from pathlib import Path

from agent_guard.analyzers import Context
from agent_guard.analyzers.secrets import SecretScanner
from agent_guard.config import AgentGuardConfig
from agent_guard.diff import parse_diff_text
from tests.conftest import make_diff


def _ctx(tmp_path: Path, diff_text: str) -> Context:
    return Context(
        repo_root=tmp_path,
        changes=parse_diff_text(diff_text, repo_root=tmp_path),
        config=AgentGuardConfig(),
    )


def test_detects_aws_access_key(tmp_path: Path) -> None:
    diff = make_diff("config.py", ['AWS_KEY = "AKIAIOSFODNN7EXAMPLE"'])
    findings = list(SecretScanner().analyze(_ctx(tmp_path, diff)))
    assert any(f.rule_id == "secrets.aws-access-key" for f in findings)


def test_detects_anthropic_key(tmp_path: Path) -> None:
    diff = make_diff("settings.py", ['client = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz1234567890"'])
    findings = list(SecretScanner().analyze(_ctx(tmp_path, diff)))
    assert any(f.rule_id == "secrets.anthropic-key" for f in findings)


def test_ignores_clean_code(tmp_path: Path) -> None:
    diff = make_diff("foo.py", ["x = 1", "y = 'hello world'"])
    findings = list(SecretScanner().analyze(_ctx(tmp_path, diff)))
    assert findings == []


def test_redaction_does_not_leak_full_secret(tmp_path: Path) -> None:
    diff = make_diff("a.py", ['key = "AKIAIOSFODNN7EXAMPLE"'])
    findings = list(SecretScanner().analyze(_ctx(tmp_path, diff)))
    assert findings
    assert "AKIAIOSFODNN7EXAMPLE" not in findings[0].evidence
