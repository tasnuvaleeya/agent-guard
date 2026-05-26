from pathlib import Path

from agent_guard.analyzers import Context
from agent_guard.analyzers.dangerous_patterns import DangerousPatternScanner
from agent_guard.config import AgentGuardConfig
from agent_guard.diff import parse_diff_text
from tests.conftest import make_diff


def _ctx(tmp_path: Path, path: str, lines: list[str]) -> Context:
    # Write the file to disk so AST analysis can read it.
    full = tmp_path / path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text("\n".join(lines))
    diff = make_diff(path, lines)
    return Context(
        repo_root=tmp_path,
        changes=parse_diff_text(diff, repo_root=tmp_path),
        config=AgentGuardConfig(),
    )


def test_flags_eval(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, "danger.py", ["x = eval(user_input)"])
    findings = list(DangerousPatternScanner().analyze(ctx))
    assert any(f.rule_id == "dangerous.eval-call" for f in findings)


def test_flags_subprocess_shell_true(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, "run.py", ["import subprocess", "subprocess.run('ls', shell=True)"])
    findings = list(DangerousPatternScanner().analyze(ctx))
    assert any(f.rule_id == "dangerous.subprocess-shell-true" for f in findings)


def test_flags_verify_false_in_any_file(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, "net.py", ["requests.get(url, verify=False)"])
    findings = list(DangerousPatternScanner().analyze(ctx))
    assert any(f.rule_id == "dangerous.disable-tls-verify" for f in findings)


def test_ignores_safe_yaml_load(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, "cfg.py", ["import yaml", "yaml.load(s, Loader=yaml.SafeLoader)"])
    findings = list(DangerousPatternScanner().analyze(ctx))
    assert not any(f.rule_id == "dangerous.yaml-unsafe-load" for f in findings)
