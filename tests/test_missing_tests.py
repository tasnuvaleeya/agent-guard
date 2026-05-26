from pathlib import Path

from agent_guard.analyzers import Context
from agent_guard.analyzers.missing_tests import MissingTestsAnalyzer
from agent_guard.config import AgentGuardConfig
from agent_guard.diff import parse_diff_text
from tests.conftest import make_diff


def _ctx(tmp_path: Path, diff_text: str) -> Context:
    return Context(
        repo_root=tmp_path,
        changes=parse_diff_text(diff_text, repo_root=tmp_path),
        config=AgentGuardConfig(),
    )


def test_flags_source_only_diff(tmp_path: Path) -> None:
    body = [f"x_{i} = {i}" for i in range(40)]
    ctx = _ctx(tmp_path, make_diff("src/app/feature.py", body))
    findings = list(MissingTestsAnalyzer().analyze(ctx))
    assert any(f.rule_id == "tests.missing" for f in findings)


def test_skipped_when_tests_changed_too(tmp_path: Path) -> None:
    body = [f"x_{i} = {i}" for i in range(40)]
    diff = make_diff("src/app/feature.py", body) + make_diff("tests/test_feature.py", ["def test_x(): assert True"])
    ctx = _ctx(tmp_path, diff)
    findings = list(MissingTestsAnalyzer().analyze(ctx))
    assert findings == []


def test_below_threshold_not_flagged(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, make_diff("src/app/feature.py", ["x = 1"]))
    findings = list(MissingTestsAnalyzer().analyze(ctx))
    assert findings == []
