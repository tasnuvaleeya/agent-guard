# Hacker News — Show HN

**Title** (≤80 chars):

```
Show HN: agent-guard – catches AI-generated code mistakes in pull requests
```

**URL field:**

```
https://github.com/tasnuvaleeya/agent-guard
```

**Body** (plain text, no markdown — HN strips it):

```
I kept noticing that Claude/Copilot/Cursor would happily generate code with hallucinated imports, eval() calls, swallowed exceptions, or test-skipping shortcuts — and these slipped past me on PR review because the diff "looked plausible." I built agent-guard to catch them deterministically in CI.

It's a GitHub Action (and a CLI) that scans PR diffs for five categories of AI-smell:

- Leaked secrets (regex + Shannon entropy, 15+ patterns)
- Hallucinated Python imports (AST-resolves against stdlib, declared deps, local modules)
- Dangerous patterns (eval, subprocess(shell=True), pickle.load, yaml.load w/o SafeLoader, etc.)
- Source-file changes without test changes
- Edits to infra/auth files (workflows, Terraform, k8s, .env)

Runs in <10s on typical PRs, no LLM call, no external service. Posts a single sticky comment with a 0–100 risk score. Tune via .agent-guard.yml or block merges via branch protection.

Repo: https://github.com/tasnuvaleeya/agent-guard
Marketplace: https://github.com/marketplace/actions/agent-guard-pr-scan
PyPI: https://pypi.org/project/ag-scan/

This is M1 — Python-only for hallucinated imports, all other analyzers are language-agnostic. M2 brings tree-sitter for JS/TS/Go/Rust/Java, baseline mode, and SARIF. Plugin SDK + opt-in LLM verdict layer in M3.

Happy to take feedback on rule false-positive rates, naming, or anything else. Source is Apache-2.0.
```

**Notes on posting:**
- Post on a Tuesday–Thursday between 8–10 AM US Pacific for best HN attention
- Be ready to reply quickly to top-of-thread questions in the first 30 minutes — early comment engagement drives ranking
- Have a screenshot ready in case someone asks "what does it look like"
