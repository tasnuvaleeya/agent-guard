# dev.to post

**Title:**
```
I built a CI tool that catches AI coding assistants' favorite mistakes
```

**Tags:** `#github`, `#python`, `#ai`, `#ciCd`, `#showdev`

**Cover image:** use `docs/images/snapshot.png`

---

**Body:**

```markdown
A few weeks ago I noticed something: Claude, Copilot, and Cursor were happily generating code that looked plausible but was subtly broken — and my PR reviews were missing it.

The patterns kept repeating:

- An import from a package that doesn't exist (`from totally_made_up_pkg import sparkle`)
- An `eval(user_input)` slipped into what looked like a clean utility
- Tests "updated" by changing `==` to `assert True`
- Permissions broadened to `0.0.0.0/0` because the AI couldn't figure out what subnet should actually be open
- A `.env` file committed with a real API key in it

None of these are exotic. They're the kind of mistake that's easy to make when you're working fast, and easy to miss in code review because the diff "looks plausible." But AI assistants make them at a much higher rate than human developers, because the assistant doesn't know what your project actually has installed, or which API key is real, or whether a function should be tested.

So I built [**agent-guard**](https://github.com/tasnuvaleeya/agent-guard) — a deterministic CI tool that catches these in pull requests.

## What it does

agent-guard is a GitHub Action (and a CLI). On every PR, it scans the diff for five categories of "AI-smell":

### 1. Leaked secrets

Fifteen high-precision regex patterns (AWS, GCP, GitHub PAT, OpenAI, Anthropic, Stripe, Slack, …) plus a Shannon-entropy fallback in `.env*` files. Evidence in reports is **redacted** — agent-guard never prints a full secret back to the PR.

### 2. Hallucinated Python imports

This is the one no other tool I know of catches. agent-guard parses your Python files with `ast`, extracts top-level imports, and verifies each against:

- stdlib (`sys.stdlib_module_names`)
- declared deps in `requirements.txt`, `pyproject.toml`
- local modules in your repo

If an import doesn't resolve in any of those, it's flagged. Built-in alias map handles the common `import cv2` ↔ `opencv-python` cases.

### 3. Dangerous patterns

AST-based for Python, regex for cross-language. Catches `eval` / `exec`, `subprocess(shell=True)`, `pickle.load`, `yaml.load` without SafeLoader, `verify=False`, `0.0.0.0` binds, `chmod 777`, `permissions: write-all` in GitHub Actions workflows, and more.

### 4. Missing tests

A simple heuristic: if a PR adds more than 30 lines to source files but touches zero test files, flag it.

### 5. Infrastructure / auth changes

Pure path matching for edits to `.github/workflows/*`, Dockerfiles, Terraform, k8s manifests, `.env*`, lockfile removals, Makefile deploy targets. These get an automatic "you sure?" flag.

## What it doesn't do

agent-guard is deliberately small. No LLM call. No external service. No telemetry. No vector DB. No web UI. It runs on Python's stdlib `ast` module plus regex, scans only the diff (not your whole repo), and finishes in under 10 seconds on typical PRs.

That makes it suitable for branch protection — set a risk-score threshold in `.agent-guard.yml`, and CI fails for any PR above it. Combine with required-checks-to-merge and you have a real safety rail.

## What it looks like

Every PR gets a sticky comment with a risk score and a categorized list of findings:

![Sample agent-guard PR comment](https://github.com/tasnuvaleeya/agent-guard/raw/main/docs/images/snapshot.png)

The comment uses GitHub's `<!-- agent-guard -->` HTML marker. On every subsequent push, the same comment is edited in place — no duplicate-comment spam.

## Try it

GitHub Action (one workflow file):

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
        with: { fetch-depth: 0 }
      - uses: tasnuvaleeya/agent-guard@v0.1.5
```

CLI:

```bash
pip install ag-scan
agent-guard scan --base main
```

The full reference (every CLI flag, every rule with severity and trigger, full config schema, CI recipes, troubleshooting, FAQ) is in the [user manual](https://github.com/tasnuvaleeya/agent-guard/blob/main/docs/USER_MANUAL.md).

## What's next

This is Milestone 1 — Python-only for hallucinated imports, all other analyzers language-agnostic. Coming up:

- **M2**: tree-sitter for JS/TS/Go/Rust/Java, baseline mode (only new findings), full SARIF for GitHub code scanning
- **M3**: AI-smell rules (bare-except swallows, stub implementations, weakened assertions, duplicate-block detection), plugin SDK for custom analyzers, opt-in LLM verdict layer with prompt caching
- **M4**: YAML policy engine, IaC rule pack, audit log, inline `# agent-guard: ignore` suppressions, LSP server

The whole roadmap is in [`features/agent-guard-feature-plan.md`](https://github.com/tasnuvaleeya/agent-guard/blob/main/features/agent-guard-feature-plan.md) — feedback welcome.

Apache-2.0. ⭐ if it'd help your team.

---

**Repo:** https://github.com/tasnuvaleeya/agent-guard
**Marketplace:** https://github.com/marketplace/actions/agent-guard-pr-scan
**PyPI:** https://pypi.org/project/ag-scan/
```

**Notes:**
- dev.to readers respond well to concrete examples — embed the screenshot at least once
- Don't over-edit; the conversational tone is fine
- Cross-post to Hashnode and Medium after dev.to is up
