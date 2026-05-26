# agent-guard User Manual

> Complete reference for installing, running, and tuning agent-guard. For a 30-second pitch and one-line setup, see the [README](../README.md). For the long-term roadmap, see [`features/agent-guard-feature-plan.md`](../features/agent-guard-feature-plan.md).

## Table of contents

1. [What agent-guard does](#1-what-agent-guard-does)
2. [Installation](#2-installation)
3. [Running scans](#3-running-scans)
4. [Configuration](#4-configuration)
5. [Rule catalog](#5-rule-catalog)
6. [Output formats](#6-output-formats)
7. [Risk scoring](#7-risk-scoring)
8. [CI recipes](#8-ci-recipes)
9. [Troubleshooting](#9-troubleshooting)
10. [FAQ](#10-faq)
11. [What's next](#11-whats-next)

---

## 1. What agent-guard does

agent-guard scans pull-request diffs (or local `git diff` output) for the kinds of mistakes AI coding assistants commonly make:

- **Leaked secrets** — pasted API keys, hardcoded credentials, `.env` files committed by accident
- **Hallucinated imports** — Python imports the assistant invented that don't exist in stdlib, your declared deps, or your codebase
- **Dangerous patterns** — `eval`, `exec`, `subprocess(shell=True)`, `pickle.load`, `yaml.load` without SafeLoader, `verify=False`, `permissions: write-all`, etc.
- **Missing tests** — source-file deltas without any test changes
- **Infrastructure/auth changes** — edits to CI workflows, Dockerfiles, Terraform, k8s manifests, `.env*` files

Each finding gets a severity (`low` / `medium` / `high` / `critical`); the report aggregates them into a 0–100 risk score and renders as either Markdown (for PR comments) or JSON (for tooling).

agent-guard is **deterministic** — no LLM call, no external service, no telemetry. M1 runs entirely on Python's stdlib `ast` module plus a handful of regex rules. Multi-language tree-sitter support and opt-in LLM verdicts arrive in later milestones.

## 2. Installation

### 2.1 As a GitHub Action

Create `.github/workflows/agent-guard.yml`:

```yaml
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
          fetch-depth: 0     # needed for base...head diff
      - uses: tasnuvaleeya/agent-guard@v0.1
```

That's all. `fetch-depth: 0` is the only easy-to-miss detail — without it, `git diff base...HEAD` won't have both endpoints.

### 2.2 As a CLI

```bash
pip install ag-scan          # PyPI distribution name (see note below)
agent-guard --version
```

> **Distribution name vs CLI name.** The PyPI package is `ag-scan` because the bare `agent-guard` name on PyPI was taken by an unrelated project. The CLI command, the GitHub Action, and everything else stay as `agent-guard`.

Python 3.11+ required. For development:

```bash
git clone https://github.com/tasnuvaleeya/agent-guard
cd agent-guard
pip install -e ".[dev]"
pytest
```

## 3. Running scans

### 3.1 In CI

Once the workflow above is in place, every PR triggers a scan automatically. A sticky comment marked with `<!-- agent-guard -->` appears on the PR — subsequent pushes edit that same comment in place rather than spamming new ones.

If the risk score exceeds `fail_above` (default `60`), the job exits non-zero, turning CI red. Combine with branch protection to block merges — see [§8.1](#81-required-check-via-branch-protection).

### 3.2 Locally

```bash
# Compare your current branch against main:
agent-guard scan --base main

# Use a custom head:
agent-guard scan --base v1.0 --head v1.1

# Pipe a diff via stdin:
git diff main | agent-guard scan

# Read a diff from a file:
agent-guard scan --diff /tmp/patch.diff

# Save JSON for downstream tooling:
agent-guard scan --base main --format json --output report.json

# Override threshold for a stricter local gate than CI:
agent-guard scan --base main --fail-above 30

# Point at a config outside the repo root:
agent-guard scan --base main --config /etc/agent-guard.yml
```

#### Full flag reference

| Flag | Type | Default | Purpose |
|---|---|---|---|
| `--diff PATH` | file | — | Read unified diff from this path |
| `--base REF` | git ref | — | Compute diff as `git diff <base>...<head>` |
| `--head REF` | git ref | `HEAD` | Head ref (used with `--base`) |
| `--repo-root PATH` | dir | `$PWD` | Repo root; used to load deps and file contents |
| `--config PATH` | file | `<repo-root>/.agent-guard.yml` | Config file |
| `--format md\|json` | choice | `md` | Report format |
| `--output PATH` | file | stdout | Write report to file instead of stdout |
| `--post-comment` | flag | off | Post (or update) the sticky PR comment |
| `--fail-above N` | int | from config (60) | Override risk-score gate |
| `--version` | flag | — | Print version and exit |

Exit codes:
- `0` — score ≤ `fail_above`
- `1` — score > `fail_above`, or a CLI / config error occurred

If no diff source is given (`--diff`, `--base`, or piped stdin), the CLI errors out — agent-guard never silently "passes" because it had nothing to scan.

### 3.3 As a pre-commit / pre-push hook

There's no formal hook wrapper in M1, but one shell line does the job:

```bash
# .git/hooks/pre-push (chmod +x it)
#!/usr/bin/env bash
agent-guard scan --base origin/main --fail-above 60 || exit 1
```

Or via the [`pre-commit`](https://pre-commit.com/) framework, with a local hook entry:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: agent-guard
        name: agent-guard
        language: system
        pass_filenames: false
        entry: bash -c 'agent-guard scan --base origin/main --fail-above 60'
```

A first-class `pre-commit` hook lands in M4.

## 4. Configuration

### 4.1 `.agent-guard.yml` reference

Drop this at your repo root. All keys are optional.

```yaml
# Top-level
fail_above: 60                    # int 0-100; default 60. Score > this fails the run.
exclude:                          # globs; matched paths are skipped entirely
  - "vendor/**"
  - "**/*.generated.py"
  - "docs/**"
include: []                       # if non-empty, only these globs are scanned

# Per-analyzer toggles and options
analyzers:
  secrets:
    enabled: true
  hallucinated_imports:
    enabled: true
  dangerous_patterns:
    enabled: true
  missing_tests:
    enabled: true
    min_added_lines: 30           # threshold below which we don't flag
    min_source_files: 1
  infra_changes:
    enabled: true
```

Anything not listed under `analyzers:` defaults to enabled with stock options. To kill a single analyzer:

```yaml
analyzers:
  missing_tests:
    enabled: false
```

### 4.2 Severity and threshold tuning

Severities are fixed per rule (see [§5](#5-rule-catalog)). You tune *risk-score sensitivity* by changing `fail_above`:

| `fail_above` | Effective gate |
|---|---|
| `0` | Any single low finding fails the run |
| `30` | One medium or one critical fails |
| `60` (default) | At least one high + one medium, or two highs, fail |
| `100` | Never blocks; comment is informational only |

### 4.3 Excluding paths

`exclude` uses gitignore-style globs and is checked against the diff path (relative to repo root). Match precedence: explicit `include` (if non-empty) > `exclude` > scanned.

```yaml
exclude:
  - "vendor/**"
  - "**/*.generated.*"
  - "tests/fixtures/**"
```

## 5. Rule catalog

Each rule has a stable `rule_id` shown in reports. Disable a whole analyzer (not an individual rule) via `.agent-guard.yml`. Per-rule severity overrides arrive in M2.

### 5.1 Secrets — `secrets.*`

15 high-precision patterns plus a Shannon-entropy fallback in `.env*` files. Evidence in reports is **redacted** (first 4 chars + ellipsis + asterisks) — agent-guard never echoes a full secret.

| Rule | Severity | Triggers on |
|---|---|---|
| `secrets.aws-access-key` | critical | `AKIA…` / `ASIA…` + 16 chars |
| `secrets.aws-secret-key` | critical | `aws_secret_access_key=…` |
| `secrets.github-pat` | critical | `ghp_`, `gho_`, `ghu_`, `ghr_`, `ghs_` tokens |
| `secrets.github-app` | critical | `github_pat_…` (fine-grained) |
| `secrets.openai-key` | critical | `sk-…` / `sk-proj-…` |
| `secrets.anthropic-key` | critical | `sk-ant-…` |
| `secrets.google-api-key` | high | `AIza…` |
| `secrets.gcp-service-account` | critical | `"type": "service_account"` |
| `secrets.stripe-key` | critical | `sk_live_…`, `rk_test_…` |
| `secrets.slack-token` | high | `xoxb-`, `xoxp-`, etc. |
| `secrets.slack-webhook` | high | `hooks.slack.com/services/…` |
| `secrets.private-key-block` | critical | `-----BEGIN …PRIVATE KEY-----` |
| `secrets.jwt` | medium | three base64url segments separated by `.` |
| `secrets.npm-token` | high | `npm_…` |
| `secrets.postgres-url` | high | `postgres://user:pass@host` |
| `secrets.high-entropy-env` | high | Shannon ≥ 4.0 value in a `.env*` file |

### 5.2 Hallucinated imports — `hallucination.*`

Python only in M1. Multi-language support lands in M2.

| Rule | Severity | Triggers on |
|---|---|---|
| `hallucination.unresolved-import` | high | An imported top-level module isn't in stdlib, `requirements.txt`/`pyproject.toml`, or local modules |

Known import-alias map handles cases where the import name differs from the dist (`cv2` ↔ `opencv-python`, `yaml` ↔ `pyyaml`, `bs4` ↔ `beautifulsoup4`, `sklearn` ↔ `scikit-learn`, etc.).

### 5.3 Dangerous patterns — `dangerous.*`

AST-based for Python (only fires on lines touched in the diff). Regex-based rules are cross-language.

| Rule | Severity | Triggers on |
|---|---|---|
| `dangerous.eval-call` | critical | `eval(...)` |
| `dangerous.exec-call` | critical | `exec(...)` |
| `dangerous.os-system` | high | `os.system(...)` |
| `dangerous.subprocess-shell-true` | high | `subprocess.*(shell=True)` |
| `dangerous.pickle-load` | high | `pickle.load(s)` / `cPickle.load(s)` |
| `dangerous.yaml-unsafe-load` | high | `yaml.load(...)` without `SafeLoader` |
| `dangerous.weak-hash` | low | `hashlib.md5` / `hashlib.sha1` |
| `dangerous.bind-all-interfaces` | medium | `0.0.0.0` literal |
| `dangerous.chmod-777` | high | `chmod 777` / `chmod -R 777` |
| `dangerous.curl-pipe-bash` | high | `curl … \| sh` |
| `dangerous.permissions-write-all` | high | GitHub Action `permissions: write-all` |
| `dangerous.disable-tls-verify` | high | `verify=False`, `rejectUnauthorized: false`, `--insecure` |

### 5.4 Missing tests — `tests.*`

| Rule | Severity | Triggers on |
|---|---|---|
| `tests.missing` | medium | `≥ min_added_lines` (default 30) added across source files with zero test files changed |

Test paths recognized: `tests/`, `test_*.py`, `__tests__/`, `*.test.{ts,tsx,js,jsx}`, `*.spec.{ts,tsx,js,jsx}`, `*_test.go`. Excluded source paths: `docs/`, `examples/`, `scripts/`, `tools/`, `vendor/`, `third_party/`, `.github/`, `node_modules/`.

### 5.5 Infrastructure changes — `infra.*`

Pure path matching — fires on any change to deployment-relevant files.

| Rule | Severity | Triggers on |
|---|---|---|
| `infra.env-file` | critical | `.env`, `.env.*` |
| `infra.workflow` | high | `.github/workflows/*.yml` |
| `infra.action-yml` | high | `action.yml` / `action.yaml` |
| `infra.terraform` | high | `*.tf`, `*.tfvars` |
| `infra.kubernetes` | high | `k8s/`, `kubernetes/`, `manifests/`, `charts/` |
| `infra.helm` | high | `charts/**.tpl`, etc. |
| `infra.dockerfile` | medium | `Dockerfile*` |
| `infra.makefile-deploy` | medium | `Makefile` |
| `infra.ci-config` | medium | CircleCI / GitLab CI / Azure Pipelines / Jenkinsfile |
| `infra.lockfile-removed` | medium | Lockfile deletion (npm/pnpm/yarn/poetry/uv/cargo/go) |

## 6. Output formats

### 6.1 Markdown (default)

Designed for posting as a sticky PR comment. Begins with the marker comment `<!-- agent-guard -->` so the action can find and edit it on subsequent runs.

```markdown
<!-- agent-guard -->
## agent-guard
**Risk score:** `100/100` — 🛑 CRITICAL

| 🛑 Critical | ⚠️ High | 🟡 Medium | ℹ️ Low |
|---|---|---|---|
| 3 | 2 | 0 | 0 |

### 🔐 Secrets (3)
- 🛑 **secrets.aws-access-key** — `src/app.py:5`
  - Possible AWS access key committed to repo
  - <details><summary>evidence</summary><pre>AKIA…****</pre></details>
...
```

### 6.2 JSON

Stable, versioned schema for downstream tooling.

```json
{
  "version": 1,
  "score": 100,
  "grade": "CRITICAL",
  "severity_counts": {"critical": 3, "high": 2, "medium": 0, "low": 0},
  "category_counts": {"secret": 3, "dangerous": 2},
  "findings": [
    {
      "rule_id": "secrets.aws-access-key",
      "severity": "critical",
      "file": "src/app.py",
      "line": 5,
      "message": "Possible AWS access key committed to repo",
      "evidence": "AKIA…****",
      "category": "secret",
      "suggested_fix": null,
      "metadata": {}
    }
  ]
}
```

Example tooling uses:

```bash
# All criticals:
agent-guard scan --base main --format json | jq '.findings[] | select(.severity == "critical")'

# Count by category:
agent-guard scan --base main --format json | jq '.category_counts'

# Fail in custom logic:
score=$(agent-guard scan --base main --format json | jq .score)
[[ "$score" -gt 40 ]] && echo "Too risky" && exit 1
```

## 7. Risk scoring

```
score = min(100, Σ severity_weight)
```

Weights: `critical = 40`, `high = 20`, `medium = 8`, `low = 2`.

| Score | Grade |
|---|---|
| 0 | CLEAN |
| 1–29 | LOW |
| 30–59 | MEDIUM |
| 60–79 | HIGH |
| 80–100 | CRITICAL |

The default `fail_above: 60` means: **two highs** (40), **one critical + one medium** (48), or **one critical + one high** (60 — passes) won't trip CI, but **one critical + two highs** (80) will. Tune to taste.

## 8. CI recipes

### 8.1 Required check via branch protection

1. Add the workflow above so the `scan` job runs on every PR.
2. In repo Settings → Branches → Branch protection rules → Add rule for `main`.
3. Enable **Require status checks to pass before merging**.
4. Find `scan` in the check list and require it.

Now PRs with risk score > `fail_above` cannot be merged.

### 8.2 Running only on certain paths

```yaml
on:
  pull_request:
    paths:
      - "src/**"
      - "tests/**"
      - "!docs/**"
```

### 8.3 Fork PRs — known limitation

PRs from external forks run with a restricted `GITHUB_TOKEN` that **cannot post comments**. Two options:

- **Recommended**: use `pull_request_target` for the comment step only, and `pull_request` for the scan itself. Be aware of the security implications (the target event has write access to the base repo).
- **Simpler**: accept that fork PRs get a red check but no comment. Maintainers see findings in the job logs.

A first-class solution lands in M2.

### 8.4 Monorepo with multiple Python projects

Set `--repo-root` to the subproject containing `requirements.txt` / `pyproject.toml`, so hallucinated-import detection resolves correctly:

```yaml
- uses: tasnuvaleeya/agent-guard@v0.1
  with:
    config: services/api/.agent-guard.yml
```

Or run the action multiple times with different roots, one per subproject. Native monorepo awareness lands in M2.

### 8.5 Custom failure threshold per branch

```yaml
- uses: tasnuvaleeya/agent-guard@v0.1
  with:
    fail-above: ${{ github.base_ref == 'main' && '40' || '80' }}
```

Strict on `main`, lenient on feature branches.

### 8.6 Disable the comment, keep the check

```yaml
- uses: tasnuvaleeya/agent-guard@v0.1
  with:
    post-comment: "false"
```

Useful when you'd rather inspect findings in the action log.

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `agent-guard: no diff supplied …` | Missing `fetch-depth: 0` in `actions/checkout` | Add `with: { fetch-depth: 0 }` |
| `agent-guard: empty diff, nothing to scan.` | Base and head resolve to the same commit | Verify the PR has commits ahead of base |
| Comment never appears | Missing `pull-requests: write` permission, or PR from a fork | Add the `permissions:` block; see [§8.3](#83-fork-prs--known-limitation) |
| `agent-guard: analyzer X errored: …` on stderr | One analyzer hit an exception | Scan continues with the other four; please file an issue with a minimal repro |
| Too many `hallucination.unresolved-import` findings | Monorepo with deps elsewhere, or non-Python project | Disable in `.agent-guard.yml` (`hallucinated_imports.enabled: false`); proper multi-language support arrives in M2 |
| Too many `tests.missing` findings | Generated/vendored code in `src/` | Add to `exclude:` globs |
| `git diff` fails inside the Action | Shallow checkout | `fetch-depth: 0` (yes, this one again) |
| `agent-guard --version` works but `agent-guard scan` says "command not found" | A `scan` script shadowed it | Use `python -m agent_guard scan …` |
| The risk score "seems off" | Severity weights aren't your taste yet | Inspect with `--format json` to see what's contributing; tune `fail_above` |

## 10. FAQ

**Does agent-guard call any external service?**
No. Default M1 runs entirely on stdlib + local rule data. No telemetry, no API key required. The optional M3 LLM verdict layer (when shipped) is off by default and uses *your* API key if enabled.

**Does it work on languages other than Python?**
For the secret scanner, dangerous-pattern regex rules, missing-tests heuristic, and infra-change detector — yes, any language. For Python AST analysis and hallucinated-import detection — Python only in M1. Tree-sitter for JS/TS/Go/Rust/Java lands in M2.

**Does it block PRs?**
Only if you enable branch protection to require the check. agent-guard's own exit code goes red when `score > fail_above`; whether that blocks merging is up to your branch protection rules.

**Can I write my own rules?**
Not in M1. A plugin SDK with entry-point-based analyzer registration lands in M3.

**Can I suppress one finding inline?**
Not in M1. You can disable an entire analyzer in `.agent-guard.yml`. Inline `# agent-guard: ignore` comments arrive in M4.

**Does it auto-fix anything?**
No. Findings are advisory. Suggested-fix patches in PR comments land in M3.

**How is it different from semgrep / gitleaks / ruff?**
agent-guard is purpose-built for **diffs of AI-generated code** — it flags hallucinated imports (no other tool does this), and its rule set is tuned to the failure modes of Claude / Codex / Cursor / Copilot output rather than general-purpose static analysis. Use it *alongside* general linters, not instead of them.

**Will there be a hosted version?**
Not in the M1–M4 roadmap. The OSS-first design is the strategic moat.

**Is the JSON schema stable?**
The top-level fields (`version`, `score`, `grade`, `severity_counts`, `category_counts`, `findings[]`) are stable in M1 and will be versioned via the `"version"` integer. Within `findings[].metadata`, fields may evolve and aren't part of the stability contract.

**Why does the comment use HTML `<details>` blocks?**
GitHub renders them inline as collapsible sections, keeping the comment short while preserving evidence for review.

**Where does the version number come from?**
`agent_guard.__version__` in `src/agent_guard/__init__.py`. Releases tag the commit and publish to PyPI via the `.github/workflows/release.yml` workflow.

## 11. What's next

Future milestones (see [`features/agent-guard-feature-plan.md`](../features/agent-guard-feature-plan.md) for the full plan):

- **M2 — CI Intelligence**: tree-sitter for JS/TS/Go/Rust/Java, baseline mode (only new findings), full SARIF, registry-resolved deps
- **M3 — Semantic Analysis**: AI-smell rules (bare-except swallows, stub implementations, weakened assertions, duplicate-block detection), plugin SDK, opt-in LLM verdict layer with prompt caching
- **M4 — Enterprise Policies**: YAML policy engine, IaC rule pack, audit log, inline suppression, LSP server for editors
