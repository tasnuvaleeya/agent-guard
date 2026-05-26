"""agent-guard command-line interface."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TextIO

import click

from agent_guard import __version__
from agent_guard.analyzers import Context, get_analyzers
from agent_guard.config import AgentGuardConfig
from agent_guard.diff import parse_diff_text
from agent_guard.models import Finding
from agent_guard.report import render_json, render_markdown
from agent_guard.scoring import score_findings


@click.group(invoke_without_command=False)
@click.version_option(__version__, prog_name="agent-guard")
def main() -> None:
    """agent-guard — CI/CD safety analysis for AI-assisted code."""


@main.command()
@click.option(
    "--diff", "diff_path", type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Read unified diff from this file. Defaults to stdin if neither --diff nor --base is given.",
)
@click.option(
    "--base", "base_ref", default=None,
    help="Base git ref. Diff is computed as `git diff <base>...<head>`.",
)
@click.option(
    "--head", "head_ref", default="HEAD",
    help="Head git ref (used with --base). Defaults to HEAD.",
)
@click.option(
    "--repo-root", type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path.cwd(),
    help="Repository root, used for resolving deps and reading file content.",
)
@click.option(
    "--config", "config_path", type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Path to .agent-guard.yml. Defaults to <repo-root>/.agent-guard.yml if present.",
)
@click.option(
    "--format", "output_format",
    type=click.Choice(["md", "json"], case_sensitive=False),
    default="md",
    help="Report format.",
)
@click.option(
    "--output", "output_path", type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write report to this file. Defaults to stdout.",
)
@click.option(
    "--post-comment", is_flag=True,
    help="Post (or update) a sticky comment on the current GitHub PR.",
)
@click.option(
    "--fail-above", type=int, default=None,
    help="Override config: exit non-zero when risk score exceeds this threshold.",
)
def scan(
    diff_path: Path | None,
    base_ref: str | None,
    head_ref: str,
    repo_root: Path,
    config_path: Path | None,
    output_format: str,
    output_path: Path | None,
    post_comment: bool,
    fail_above: int | None,
) -> None:
    """Scan a unified diff and emit a risk report."""
    repo_root = repo_root.resolve()
    config = AgentGuardConfig.load(config_path or (repo_root / ".agent-guard.yml"))
    if fail_above is not None:
        config.fail_above = fail_above

    diff_text = _read_diff(diff_path, base_ref, head_ref, repo_root)
    if not diff_text.strip():
        click.echo("agent-guard: empty diff, nothing to scan.", err=True)
        _emit_empty_report(output_format, output_path)
        sys.exit(0)

    changes = parse_diff_text(diff_text, repo_root=repo_root)
    ctx = Context(repo_root=repo_root, changes=changes, config=config)

    findings: list[Finding] = []
    for analyzer in get_analyzers(config):
        try:
            findings.extend(analyzer.analyze(ctx))
        except Exception as exc:
            click.echo(f"agent-guard: analyzer `{analyzer.id}` errored: {exc}", err=True)

    score = score_findings(findings)
    report = render_markdown(findings, score) if output_format == "md" else render_json(findings, score)

    if output_path:
        output_path.write_text(report)
    else:
        click.echo(report)

    if post_comment:
        from agent_guard.github import post_sticky_comment

        try:
            url = post_sticky_comment(render_markdown(findings, score))
            click.echo(f"agent-guard: posted comment → {url}", err=True)
        except Exception as exc:
            click.echo(f"agent-guard: failed to post comment: {exc}", err=True)

    if score.score > config.fail_above:
        click.echo(
            f"agent-guard: risk score {score.score} exceeds threshold {config.fail_above}",
            err=True,
        )
        sys.exit(1)


def _read_diff(
    diff_path: Path | None,
    base_ref: str | None,
    head_ref: str,
    repo_root: Path,
) -> str:
    if diff_path is not None:
        return diff_path.read_text()
    if base_ref is not None:
        cmd = ["git", "-C", str(repo_root), "diff", "--no-color", f"{base_ref}...{head_ref}"]
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            raise click.ClickException(f"`git diff` failed: {exc}") from exc
        return result.stdout
    if sys.stdin.isatty():
        raise click.ClickException(
            "no diff supplied — pass --diff <file>, --base <ref>, or pipe a diff on stdin."
        )
    return sys.stdin.read()


def _emit_empty_report(output_format: str, output_path: Path | None) -> None:
    findings: list[Finding] = []
    score = score_findings(findings)
    report = render_markdown(findings, score) if output_format == "md" else render_json(findings, score)
    if output_path:
        output_path.write_text(report)
    else:
        click.echo(report)


# Allow `python -m agent_guard` for convenience.
def _module_main(argv: list[str] | None = None, stdout: TextIO | None = None) -> None:  # pragma: no cover
    main(argv)


if __name__ == "__main__":  # pragma: no cover
    main()
