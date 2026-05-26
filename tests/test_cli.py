from pathlib import Path

from click.testing import CliRunner

from agent_guard.cli import main
from tests.conftest import make_diff


def test_scan_reads_diff_file(tmp_path: Path) -> None:
    diff_file = tmp_path / "patch.diff"
    diff_file.write_text(make_diff("app.py", ['key = "AKIAIOSFODNN7EXAMPLE"']))

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["scan", "--diff", str(diff_file), "--repo-root", str(tmp_path), "--format", "json", "--fail-above", "0"],
    )
    # --fail-above 0 forces non-zero exit when any finding fires
    assert result.exit_code == 1
    assert "secrets.aws-access-key" in result.output


def test_scan_clean_diff_is_zero_exit(tmp_path: Path) -> None:
    diff_file = tmp_path / "patch.diff"
    diff_file.write_text(make_diff("app.py", ["x = 1"]))

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["scan", "--diff", str(diff_file), "--repo-root", str(tmp_path), "--format", "json"],
    )
    assert result.exit_code == 0
