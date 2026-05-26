# agent-guard — Feature Plan

A CI/CD safety and risk analysis tool for AI-assisted coding workflows (Claude Code, Codex, Cursor, Copilot, etc.).

The tool analyzes pull requests and git diffs, detects risky AI-generated code patterns, flags hallucinated imports/APIs, detects missing tests, identifies dangerous infrastructure/auth changes, scans for secrets, generates risk scores, comments on GitHub PRs, and acts as a safety rail for AI-assisted development.

**Constraints:** Python-based · GitHub Action first · deterministic analysis first · LLM features only after MVP · optimized for open-source adoption · fast execution (<10s preferred) · modular analyzer architecture.

**Prefer:** AST analysis · tree-sitter · rule engines · practical heuristics · clean CLI UX.

**Avoid:** vector DBs · microservices · Kubernetes · dashboards · user auth · unnecessary cloud infrastructure.

---

# Milestone 1 — MVP

**Goal:** A working GitHub Action + CLI that analyzes a PR diff with deterministic Python analyzers and posts a single risk-scored comment. No LLM. Runs in <10s on typical PRs.

**Core Features:**
- `agent-guard scan` CLI that takes a unified diff (stdin, file, or `--base/--head` git refs) and emits JSON + Markdown reports
- Five deterministic analyzers:
  1. **SecretScanner** — regex + entropy (Shannon ≥ 4.0 on candidate substrings); 15–20 high-precision patterns (AWS, GCP, Slack, GitHub PAT, OpenAI, Anthropic, generic high-entropy strings in `.env*`, `*.yml`, code)
  2. **HallucinatedImportScanner (Python only, MVP)** — parse added Python files with `ast`, extract top-level imports, verify each against (a) stdlib list, (b) project's `requirements.txt`/`pyproject.toml`/`uv.lock`, (c) local module map. Anything unresolved = flagged
  3. **DangerousPatternScanner** — AST rules for `eval`, `exec`, `subprocess(..., shell=True)`, `pickle.loads` on untrusted input, `os.system`, `yaml.load` w/o SafeLoader, `requests.get(verify=False)`, hardcoded `0.0.0.0` bindings
  4. **MissingTestsAnalyzer** — heuristic: if added/modified lines in `src/` or top-level package dirs exceed N lines and no files under `tests/` or `test_*.py` changed → flag. Ratio-based, not absolute
  5. **InfraChangeDetector** — pure path-based: any change to `.github/workflows/*`, `Dockerfile*`, `*.tf`, `k8s/`, `helm/`, `.env*`, `package.json` `scripts`, `Makefile` deploy targets → flag with severity tag
- **RiskScorer** — weighted sum, capped 0–100. Severity weights: critical=40, high=20, medium=8, low=2. Categories printed individually so the score is auditable
- **GitHub Action** (`action.yml` composite action) — checkout, install agent-guard, run scan against `${{ github.event.pull_request.base.sha }}...HEAD`, post sticky PR comment via `GITHUB_TOKEN`
- **Sticky comment**: idempotent — finds prior `<!-- agent-guard -->` comment and edits in place

**Technical Stack:**
- Python 3.11+, `uv` for env/build
- `ast` (stdlib), `pathspec` (gitignore-style matching), `unidiff` (parse diffs), `pydantic` v2 (config + report schema), `rich` (CLI output), `click` (CLI)
- `pytest` for tests, `ruff` + `mypy` for lint/types
- No external services. No LLM.

**Implementation Tasks:**
1. Repo scaffold + `pyproject.toml` + CI (lint, type, test on PR)
2. `agent_guard.diff` — parse unified diff → `FileChange[]` (added lines, removed lines, hunk metadata)
3. `agent_guard.analyzers.base.Analyzer` ABC + analyzer registry
4. Implement five analyzers above; each returns `Finding[]` with `(rule_id, severity, file, line, message, evidence)`
5. `agent_guard.scoring` — weighted aggregator
6. `agent_guard.report` — Markdown + JSON renderers
7. `agent_guard.cli` — `scan`, `version`, `--config` (YAML), `--format md|json|sarif-min`
8. `action.yml` + `Dockerfile` (slim python:3.11-slim, pre-installed package) — or pure composite action with `pip install agent-guard==X`
9. `examples/` repo demo + GIF in README
10. Docs: README quickstart (≤5 lines of setup), one-page rules reference

**Out of Scope:**
- Non-Python hallucination detection
- LLM-assisted analysis
- Plugin SDK
- Multi-repo / org config
- SARIF full spec (only minimal subset)
- Auto-fix / suggestions
- Caching, incremental analysis
- Web dashboard

**Release Criteria:**
- Runs on the agent-guard repo's own PRs (dogfood)
- <10s on a 500-line diff
- Zero false positives on a curated test fixture of 20 "clean" PRs
- ≥80% recall on a fixture of 20 "dirty" PRs (planted issues)
- One-command install: `pip install agent-guard` works
- GitHub Action usable via `uses: <your-org>/agent-guard@v0.1`

---

# Milestone 2 — CI Intelligence Layer

**Goal:** Multi-language support, configurable rules, and PR-aware analysis (only flag *new* issues, not pre-existing tech debt). Becomes useful on real codebases.

**Core Features:**
- **Tree-sitter integration** via `tree-sitter-languages` for Python, JS/TS, Go, Rust, Java. Hallucinated-import and dangerous-pattern analyzers ported per language
- **Package resolution per ecosystem**: `package.json` + `pnpm-lock.yaml` / `yarn.lock`, `go.mod`, `Cargo.toml`, `pom.xml`. Stretch: query registry (`pypi.org/pypi/<name>/json`, `registry.npmjs.org/<name>`) with a 200ms timeout + local cache, behind `--verify-registries` flag (off by default — keeps default run hermetic and fast)
- **Baseline mode**: `agent-guard scan --baseline main` only reports findings on lines touched in the diff; pre-existing findings suppressed
- **YAML config** (`.agent-guard.yml`):
  - Enable/disable analyzers
  - Per-rule severity overrides
  - File globs (include/exclude)
  - Custom regex patterns for SecretScanner
  - Score thresholds (`fail_above: 60`)
- **Full SARIF 2.1.0 output** — uploads to GitHub code scanning automatically
- **Severity escalation rules**: e.g., a secret in a `.env` *and* a workflow file change = critical regardless of base severity
- **Performance**: parallel analyzer execution via `concurrent.futures`, file-level memoization

**Technical Stack:**
- Add `tree-sitter`, `tree-sitter-languages`, `requests` (with timeout/retry), `diskcache` (cache registry lookups)
- Keep core dependencies minimal — tree-sitter and registry features behind extras: `pip install agent-guard[full]`

**Implementation Tasks:**
1. `agent_guard.parsers/` — unified `Parser` interface; tree-sitter wrappers per language
2. Port DangerousPatternScanner + HallucinatedImportScanner to use parser abstraction
3. `agent_guard.resolvers/` — per-ecosystem dependency resolvers
4. Registry verifier with cache, opt-in
5. `agent_guard.baseline` — clone diff between baseline ref and head, intersect findings with changed lines
6. Config loader (`pydantic`-validated YAML)
7. SARIF emitter + GitHub Action step that uploads via `github/codeql-action/upload-sarif`
8. Benchmark suite — track p50/p95 runtime across 50 OSS PR fixtures, fail CI if regressed
9. `--watch` mode for local dev (re-run on save) — improves DX, drives feedback

**Out of Scope:**
- Semantic / behavioral analysis (still pattern matching)
- LLM features
- Cross-file taint tracking
- Custom analyzers by users
- IDE plugins

**Release Criteria:**
- Five languages supported for at least secrets + dangerous patterns + hallucinated imports
- Config file documented with full schema
- SARIF appears in GitHub Security tab
- Used on ≥3 external OSS repos (recruit beta users; document findings)

---

# Milestone 3 — Semantic Analysis

**Goal:** Move from "patterns" to "behavior." Detect AI-smell signatures (over-broad exception handlers, fake stubs, copy-paste bloat, mis-scoped permissions). Introduce a plugin SDK so the community extends it. Add **opt-in** LLM verdict on high-noise findings.

**Core Features:**
- **AI-smell analyzers** (deterministic, AST-based):
  - `bare-except-swallow` — `except Exception: pass` / `catch (e) {}`
  - `stub-implementation` — function body is only `pass`, `return None`, `throw NotImplementedError`, or `// TODO` in a non-test file
  - `duplicate-block` — near-identical AST subtrees (>10 nodes) added in the same PR — classic LLM regeneration smell
  - `weakened-assertion` — test files where assertions changed from `==` to `assert truthy` or `assert True`
  - `permission-broadening` — IAM/role docs going from specific actions to `*`, `0.0.0.0/0` ingress added, `chmod 777`, k8s `privileged: true`, GitHub Action `permissions: write-all`
  - `dependency-version-drop` — version pin loosened (`==1.2.3` → `>=1.0`) or lockfile removed
- **Cross-file analysis** — call graph for added symbols; flag unused additions, dead imports
- **Plugin SDK**: third-party packages register analyzers via entry points (`agent_guard.analyzers`). Public types: `Analyzer`, `Finding`, `Context` (parsed AST, diff, config). Documented in `docs/plugin-sdk.md`. Ship 2 example plugins as separate repos.
- **Optional LLM verdict layer** (`--with-llm`, off by default):
  - Only runs on findings already triggered by deterministic rules
  - Sends *only* the offending hunk + rule context, never the whole file
  - Returns: `confirm | dismiss | needs-human` + 1-line rationale
  - Provider-pluggable (`AGENT_GUARD_LLM_PROVIDER=anthropic|openai|local`)
  - Hard token budget per run; aborts if exceeded
  - Cache by `(rule_id, hunk_hash)` to avoid re-spending
- **Suggested fixes** — for a subset of rules, emit a unified-diff patch in the PR comment as a collapsible "suggested fix" block

**Technical Stack:**
- `tree-sitter` queries (`.scm` files) for cross-language pattern reuse
- `anthropic` SDK (default provider), generic adapter for others
- `importlib.metadata` for plugin discovery
- Add prompt caching on the LLM path (cache the static rule context)

**Implementation Tasks:**
1. AI-smell analyzer pack — each rule + curated fixtures
2. Call-graph builder (lightweight, file-scope first)
3. `agent_guard.plugins` — entry point loading, sandboxing (timeout per analyzer), capability declarations
4. LLM adapter (`agent_guard.llm.Provider` ABC) + Anthropic implementation w/ prompt caching
5. Token accounting + per-run budget enforcement
6. Suggested-fix renderer
7. Public docs site (mkdocs-material), rule reference, plugin tutorial
8. Example plugins: `agent-guard-django`, `agent-guard-terraform` (separate repos, advertised in main README)

**Out of Scope:**
- Whole-repo / multi-PR memory
- Auto-applying fixes
- Vector search / embeddings
- Multi-tenant SaaS
- Auth/users

**Release Criteria:**
- At least 6 semantic analyzers shipping
- Plugin SDK has 1 docs-site tutorial and 2 working example plugins
- LLM path verified: ≤$0.02/run on median PR with caching, dismisses ≥30% of low-severity findings without losing real bugs in fixture
- Dogfooded for 4 weeks on agent-guard itself

---

# Milestone 4 — Enterprise Policies

**Goal:** Make agent-guard adoptable inside orgs with compliance/security teams. Centralized policy, audit trail, IaC awareness. Still no SaaS, no dashboards.

**Core Features:**
- **Policy engine** — YAML-based, expression language for combining findings:
  ```yaml
  policies:
    - id: block-secret-and-infra
      when: "has_finding('secret.*') and has_finding('infra.workflow')"
      action: block
      message: "Secret + workflow change combination requires security review"
  ```
  Powered by `cel-python` or a small custom evaluator — avoid OPA/Rego (too heavy for OSS adoption)
- **Org-level config inheritance** — `agent-guard` reads policies from a referenced repo (`extends: github.com/myorg/agent-guard-policies@main`) with caching + pinned-SHA verification
- **IaC analyzers**:
  - Terraform: detect public S3 buckets, open security groups, IAM `*` actions, removed `lifecycle { prevent_destroy = true }`
  - Kubernetes manifests: `privileged`, `hostNetwork`, missing resource limits, `latest` tag
  - Docker: `FROM` unpinned, running as root, ADD-from-URL
- **Auth/permission diff analyzer** — special category for changes to: `.github/workflows/*.permissions`, GitHub repo settings via API, OIDC trust policies, RBAC bindings, GitHub Apps installation files
- **Audit log** — append-only JSONL written to `.agent-guard/audit/` per run (rule version, findings, suppressions, who suppressed via `# agent-guard: ignore` comments)
- **Suppression workflow** — inline `# agent-guard: ignore rule-id reason="..."` requires non-empty reason; tracked in audit log
- **Compliance report mode** — `agent-guard report --since=<sha>` aggregates audit logs into a Markdown summary suitable for monthly review
- **Pre-commit + IDE hooks**:
  - `pre-commit` hook (already trivially possible — formalize and publish `.pre-commit-hooks.yaml`)
  - LSP server (`agent-guard lsp`) so editors get inline findings — Cursor/VSCode/Zed compatible. Keep minimal: diagnostics only, no code actions in this milestone

**Technical Stack:**
- `cel-python` (or hand-rolled expression evaluator if dependency weight matters)
- `pygls` for LSP server
- No new infrastructure dependencies

**Implementation Tasks:**
1. Policy engine + expression evaluator + 10 starter policies
2. `extends:` resolver with SHA pinning + signature check (optional GPG)
3. IaC analyzer pack (Terraform via `tree-sitter-hcl`, k8s via PyYAML schema-aware parsing)
4. Audit log writer + reader + `report` subcommand
5. Suppression parser + audit linkage
6. `pre-commit` integration
7. LSP server with diagnostic publishing
8. Docs section: "Adopting agent-guard at your org" — explicit anti-pattern guidance

**Out of Scope:**
- Hosted SaaS / multi-tenant
- User auth, SSO, RBAC inside agent-guard
- Web dashboard
- Real-time / always-on agents
- Custom-trained models
- Vulnerability scanning (defer to `pip-audit`, `npm audit`, `trivy` — integrate, don't replace)

**Release Criteria:**
- Policy engine documented with 10+ examples
- IaC pack covers Terraform + k8s + Dockerfile at parity with secrets-pack quality
- LSP works in VSCode + Cursor with screenshots in docs
- Used in production by ≥2 external orgs (case studies in README)

---

## Risks and Scope Creep Warnings

| Risk                                   | Mitigation                                                                                                                                        |
|----------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------|
| Becoming "another linter"              | Stay laser-focused on **diff-only** + **AI-generated patterns**. Reject features that overlap with ruff/eslint/semgrep unless they're AI-specific |
| LLM cost runaway in M3                 | Hard per-run token budget, deterministic-first gate, prompt caching, off by default                                                               |
| Plugin SDK lock-in (M3)                | Version the SDK separately (`agent_guard_sdk` package), semver strictly, deprecation lane                                                         |
| Registry lookups in M2 cause flakiness | Default off, short timeout, cache aggressively, never block release on a network call                                                             |
| Tree-sitter binary size in CI          | Use `tree-sitter-languages` shared wheels; pin versions; benchmark cold-start                                                                     |
| OPA/Rego temptation in M4              | Explicitly chosen against — too steep a learning cliff for OSS users                                                                              |
| Trying to detect *all* AI smells       | Each rule needs a fixture proving precision ≥90% on real diffs before merge                                                                       |
| Wandering into SaaS                    | OSS-first roadmap is your moat; any hosted offering is post-M4 and a separate repo                                                                |

## What Should Explicitly NOT Be Built Yet

- **No web UI / dashboard** — terminal + GitHub PR comment is the entire surface
- **No user accounts, auth, billing** — there is no server
- **No vector DB / embeddings / semantic code search** — you're scanning diffs, not the world
- **No background workers / queues / Redis** — GitHub Actions is the runtime
- **No multi-PR memory** — each run is stateless except for the audit log file
- **No autofix in M1–M2** — fixes only as PR comment suggestions in M3
- **No custom-trained model** — wrappers around existing LLMs only, opt-in
- **No Kubernetes / Helm chart** — install is `pip install` or GitHub Action `uses:`
- **No GraphQL / OpenAPI server** — CLI is the API

## Suggested GitHub Release Strategy

- **v0.x (M1)** — frequent (weekly during MVP), `v0.1.0` first usable release. Tag `latest` action ref. Publish to PyPI. README has one-click "Add to your repo" snippet
- **v1.0 (end M2)** — semver-stable CLI flags, config schema, JSON output. Publish to PyPI + GitHub Container Registry (slim image for the Action). Announce on HN/Reddit r/programming, dev.to post with real PR examples
- **v1.x (M3)** — plugin SDK released as a separate `agent_guard_sdk` package with its own semver. Each example plugin gets its own repo + release. Launch docs site
- **v2.0 (M4)** — policy engine breaking config additions (still backward compatible). Cut a long-term-support branch off v1.x for users who don't want enterprise features
- Every release: signed tags, generated `CHANGELOG.md`, GitHub Release with binaries (sdist + wheel + action.tar.gz), security advisories via GHSA

---

## 30-Day Build Roadmap

**Days 1–3** — Repo scaffold, `pyproject.toml`, CI (lint/type/test on PR), README skeleton, `agent_guard.diff` parser, `Analyzer` ABC, `Finding` dataclass, scoring module
**Days 4–6** — SecretScanner (regex + entropy) + 30 fixture diffs
**Days 7–9** — DangerousPatternScanner (Python AST) + fixtures
**Days 10–12** — HallucinatedImportScanner (Python, local resolution only) + fixtures
**Days 13–14** — MissingTestsAnalyzer + InfraChangeDetector + fixtures
**Day 15** — Markdown + JSON report renderers; CLI polish
**Days 16–18** — GitHub Action (`action.yml`), sticky comment poster, end-to-end test on a sandbox repo
**Day 19** — Dogfood: run on agent-guard's own commits retroactively, tune thresholds
**Days 20–22** — Benchmark harness, perf pass to hit <10s p95
**Day 23** — Docs pass (README quickstart, rules reference, FAQ)
**Day 24** — PyPI release `v0.1.0`, action tagged `v0.1`
**Days 25–27** — Run on 5 popular OSS repos' recent PRs, collect findings, tune false-positive rate
**Day 28** — Write launch post with concrete examples
**Day 29** — Submit to Hacker News + relevant subreddits
**Day 30** — Triage incoming issues, ship `v0.1.1` with the top three fixes

## Suggested Repository Structure

```
agent-guard/
├── action.yml                          # GitHub Action entry
├── pyproject.toml
├── README.md
├── CHANGELOG.md
├── LICENSE                             # Apache-2.0
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                      # lint/type/test
│   │   ├── release.yml                 # tag → PyPI
│   │   └── dogfood.yml                 # agent-guard runs on its own PRs
│   └── ISSUE_TEMPLATE/
├── src/
│   └── agent_guard/
│       ├── __init__.py
│       ├── cli.py                      # click entry, `scan`, `report`, `lsp`
│       ├── config.py                   # pydantic schema, YAML loader
│       ├── diff/
│       │   ├── parser.py               # unified-diff → FileChange
│       │   └── baseline.py             # baseline-ref intersection (M2)
│       ├── parsers/
│       │   ├── base.py                 # Parser ABC
│       │   ├── python_ast.py
│       │   └── treesitter.py           # (M2)
│       ├── resolvers/                  # (M2) per-ecosystem dep resolvers
│       │   ├── python.py
│       │   ├── node.py
│       │   └── ...
│       ├── analyzers/
│       │   ├── base.py                 # Analyzer ABC, Finding, Context
│       │   ├── registry.py
│       │   ├── secrets.py
│       │   ├── hallucinated_imports.py
│       │   ├── dangerous_patterns.py
│       │   ├── missing_tests.py
│       │   ├── infra_changes.py
│       │   └── semantic/               # (M3)
│       │       ├── bare_except.py
│       │       ├── stub_impl.py
│       │       └── ...
│       ├── llm/                        # (M3) opt-in
│       │   ├── base.py
│       │   ├── anthropic.py
│       │   └── budget.py
│       ├── policy/                     # (M4)
│       │   ├── engine.py
│       │   └── extends.py
│       ├── scoring.py
│       ├── report/
│       │   ├── markdown.py
│       │   ├── json.py
│       │   └── sarif.py                # (M2)
│       ├── github/
│       │   └── comment.py              # sticky PR comment
│       ├── audit/                      # (M4)
│       └── lsp/                        # (M4)
├── tests/
│   ├── fixtures/
│   │   ├── clean_prs/                  # 20 should-pass diffs
│   │   └── dirty_prs/                  # 20 should-flag diffs
│   ├── analyzers/
│   └── e2e/
├── docs/
│   ├── index.md
│   ├── rules/                          # one MD per rule
│   ├── plugin-sdk.md                   # (M3)
│   └── adopting-at-orgs.md             # (M4)
├── benchmarks/
│   └── run_bench.py
└── examples/
    ├── basic-workflow.yml
    └── advanced-config.yml
```

## Suggested Analyzer Plugin Interface

```python
# src/agent_guard/analyzers/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Literal

class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass(frozen=True)
class Finding:
    rule_id: str                # e.g. "secrets.aws-access-key"
    severity: Severity
    file: str                   # path relative to repo root
    line: int                   # 1-indexed; 0 if file-level
    message: str                # one-line user-facing summary
    evidence: str               # the offending snippet (redacted for secrets)
    category: str               # "secret" | "hallucination" | "dangerous" | "tests" | "infra" | "semantic" | "policy"
    suggested_fix: str | None = None   # unified diff, optional
    metadata: dict | None = None       # rule-specific extras

@dataclass(frozen=True)
class FileChange:
    path: str
    status: Literal["added", "modified", "deleted", "renamed"]
    added_lines: list[tuple[int, str]]    # (line_no, content)
    removed_lines: list[tuple[int, str]]
    full_added_content: str | None        # for AST parsing of added/modified files

@dataclass
class Context:
    repo_root: str
    changes: list[FileChange]
    config: "AgentGuardConfig"
    parsers: "ParserRegistry"             # lazy access to tree-sitter / ast
    resolvers: "ResolverRegistry"         # M2+
    cache: "Cache"                         # diskcache-backed

class Analyzer(ABC):
    id: str                                # stable, e.g. "secrets"
    rules: tuple[str, ...]                 # rule_ids this analyzer can emit
    languages: tuple[str, ...] = ("*",)    # filter; "*" = any

    @abstractmethod
    def analyze(self, ctx: Context) -> Iterable[Finding]: ...

    def configure(self, options: dict) -> None:
        """Receive analyzer-specific config from .agent-guard.yml."""
        return None
```

Plugins register via `pyproject.toml` entry points:

```toml
[project.entry-points."agent_guard.analyzers"]
django = "agent_guard_django:DjangoAnalyzer"
```

Discovery walks entry points at startup; each analyzer runs with a per-call timeout (default 2s), output validated against the `Finding` schema, exceptions captured to the report so one bad plugin can't fail the whole run.

## Top 5 Features Most Likely to Attract GitHub Stars

1. **One-line GitHub Action setup** — `uses: <your-org>/agent-guard@v1` with a sticky PR comment showing a clear risk score and findings list. This is the screenshot in the README; it sells the project in 5 seconds
2. **Hallucinated-import detection** — extremely tangible to anyone who's seen Claude/Copilot invent a `from sklearn.preprocessing import MagicScaler`. Demos beautifully and addresses a felt pain point unique to AI-generated code
3. **AI-smell pack** (M3) — bare-except swallows, stub implementations, weakened assertions, duplicate-block detection. Each one has a viral "I caught the LLM trying to skip writing the test" moment
4. **Free, deterministic, offline** — no API key required for the default ruleset. LLM is opt-in. This positions agent-guard against paid SaaS competitors and is repeatable in CI without quota anxiety
5. **Plugin SDK with real examples** (M3) — once `agent-guard-django` and `agent-guard-terraform` exist as separate repos, every framework community can spin their own and link back. Compounds stars over time