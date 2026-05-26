# Reddit — r/programming, r/devops, r/Python

**Title** (≤300 chars, no clickbait):

```
agent-guard: a GitHub Action that catches AI-generated code mistakes in PRs (hallucinated imports, eval, missing tests, leaked secrets)
```

**Body** (markdown supported):

```markdown
I noticed Claude/Copilot/Cursor confidently generate code with hallucinated imports, eval() calls, swallowed exceptions, or test-skipping shortcuts, and these slipped past me on PR review because the diff "looked plausible."

I built **agent-guard** to catch them deterministically in CI. Open-source, Apache-2.0.

## What it does

Scans PR diffs for five categories of AI-smell:

| Analyzer | Catches |
|---|---|
| `secrets` | 15+ regex patterns (AWS, GCP, GitHub PAT, OpenAI, Anthropic, Stripe) + entropy fallback in `.env*` |
| `hallucinated_imports` | Python imports not in stdlib, `requirements.txt`/`pyproject.toml`, or local modules |
| `dangerous_patterns` | `eval`, `exec`, `subprocess(shell=True)`, `pickle.load`, `yaml.load` w/o SafeLoader, `verify=False`, `permissions: write-all` |
| `missing_tests` | Source-file deltas without test changes |
| `infra_changes` | Edits to workflows, Dockerfiles, Terraform, k8s, `.env*` |

Each finding has a severity; the report aggregates them into a 0–100 risk score. Posts a sticky PR comment, updates in place on each push. Fails CI if score exceeds your threshold — combine with branch protection to block merges.

## How it's different

- **No LLM call.** Pure stdlib + regex + AST. Runs in <10s. No API key required.
- **Diff-focused.** Doesn't re-flag pre-existing tech debt — only what the current PR touches.
- **AI-smell oriented.** Hallucinated imports specifically — no other tool I know of detects these.

## Try it

GitHub Action:
```yaml
- uses: tasnuvaleeya/agent-guard@v0.1.5
```

CLI:
```bash
pip install ag-scan
agent-guard scan --base main
```

## Links

- Repo: https://github.com/tasnuvaleeya/agent-guard
- Marketplace: https://github.com/marketplace/actions/agent-guard-pr-scan
- PyPI: https://pypi.org/project/ag-scan/
- User Manual: https://github.com/tasnuvaleeya/agent-guard/blob/main/docs/USER_MANUAL.md

This is M1. M2 brings tree-sitter for JS/TS/Go/Rust/Java + baseline mode + SARIF. Plugin SDK + opt-in LLM verdict in M3.

Happy to hear feedback on rule false-positive rates, naming, what you'd want next.
```

**Where to post:**
- r/programming (~6M, broad)
- r/devops (~600k, very relevant)
- r/Python (~1.2M, mention `pip install` works on its own)
- r/CodingHelp, r/learnprogramming — only if customized for those audiences

**Subreddit etiquette:**
- One post per sub max
- Reply to mods' rules if any subreddit has automod
- Cross-post links via the actual cross-post feature, not duplicate submissions
