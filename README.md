# agent-guard

> CI/CD safety and risk analysis for AI-assisted coding workflows (Claude Code, Codex, Cursor, Copilot, …).

agent-guard scans pull request diffs for the patterns that AI coding assistants tend to slip into your repo: hallucinated imports, dangerous calls, missing tests, infra/auth changes, and leaked secrets. It runs deterministically (no LLM required), in <10s on typical diffs, and posts a single sticky comment on your PR.

## Status

Milestone 1 — MVP. Python only for hallucinated-import detection; all other analyzers are language-agnostic. See [`features/agent-guard-feature-plan.md`](features/agent-guard-feature-plan.md) for the full roadmap.

For the full reference — every CLI flag, every rule, every config key, CI recipes, troubleshooting, and FAQ — see [**`docs/USER_MANUAL.md`**](docs/USER_MANUAL.md).

## Quickstart

### As a GitHub Action

```yaml
# .github/workflows/agent-guard.yml
name: agent-guard
on: pull_request
permissions:
  contents: read
  pull-requests: write
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: tasnuvaleeya/agent-guard@v0.1
```

### Locally

```bash
pip install ag-scan                # PyPI distribution name
git diff main...HEAD | agent-guard scan --format md
```

> **Note:** the PyPI distribution name is `ag-scan` because `agent-guard` was already taken by an unrelated project. The CLI command and GitHub Action are still named `agent-guard`.

## What it flags

| Analyzer | Detects |
|---|---|
| `secrets` | AWS, GCP, Slack, GitHub PAT, OpenAI/Anthropic API keys, high-entropy strings in `.env*` |
| `hallucinated_imports` | Python imports not in stdlib, `requirements.txt`, `pyproject.toml`, or local modules |
| `dangerous_patterns` | `eval`, `exec`, `shell=True`, `pickle.loads`, `yaml.load` w/o SafeLoader, `verify=False`, `0.0.0.0` binds |
| `missing_tests` | Source-file changes without corresponding test changes |
| `infra_changes` | Edits to `.github/workflows`, Dockerfiles, Terraform, k8s manifests, `.env*` |

Each finding gets a severity (`low`/`medium`/`high`/`critical`); the report includes an aggregate risk score (0–100).

## Configuration

Drop a `.agent-guard.yml` in your repo root. All keys are optional.

```yaml
analyzers:
  secrets: { enabled: true }
  missing_tests: { enabled: true, min_added_lines: 30 }
fail_above: 60
exclude:
  - "vendor/**"
  - "**/*.generated.py"
```

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
mypy src
```

## License

Apache-2.0
