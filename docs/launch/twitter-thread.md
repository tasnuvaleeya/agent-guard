# Twitter/X thread

Each tweet ≤280 chars. Post as a single thread.

---

**Tweet 1/6** (the hook):

```
Claude, Copilot, and Cursor confidently generate code with hallucinated imports, eval() calls, and missing tests — and these slip past PR review because the diff looks plausible.

I built agent-guard to catch them in CI. Open-source. <10s. No LLM call.

🧵👇
```

**Attach image:** `docs/images/snapshot.png` (the sticky-comment screenshot)

---

**Tweet 2/6** (what it catches):

```
agent-guard scans PR diffs for 5 categories of AI-smell:

🔐 Leaked secrets (15+ regex + entropy)
🤖 Hallucinated Python imports (AST-resolves against your deps)
💣 Dangerous calls (eval, subprocess shell=True, pickle.load, ...)
🧪 Missing tests
🏗️ Infra/auth file edits

Posts a sticky PR comment.
```

---

**Tweet 3/6** (the unique-value pitch):

```
The killer feature: hallucinated-import detection.

No other tool catches `from totally_made_up_pkg import sparkle`. agent-guard parses imports with ast, then checks stdlib + your requirements.txt/pyproject.toml + local modules. Anything unresolved = flagged.

It's the AI-coding-assistant smell.
```

---

**Tweet 4/6** (the install):

```
One workflow file:

```yaml
- uses: tasnuvaleeya/agent-guard@v0.1.5
```

Or local CLI:

```
pip install ag-scan
agent-guard scan --base main
```

Sticky PR comment, 0–100 risk score, configurable threshold. Combine with branch protection to actually block bad merges.
```

---

**Tweet 5/6** (the why-trust-this):

```
What it isn't:
- No LLM call (deterministic)
- No external service or telemetry
- No web UI / SaaS
- Default ruleset runs offline

What it is:
- Python's stdlib ast + tree-sitter (coming in M2)
- Apache-2.0
- Diff-only — won't re-flag pre-existing tech debt

Designed for branch protection, not vibes.
```

---

**Tweet 6/6** (the call-to-action):

```
Try it on your repo's next AI-assisted PR:

🔗 https://github.com/tasnuvaleeya/agent-guard
📦 https://github.com/marketplace/actions/agent-guard-pr-scan
🐍 https://pypi.org/project/ag-scan/

⭐ if it'd help your team. Happy to take feedback on rule false-positive rates, naming, or what you'd want next.
```

---

**Hashtags to add to the last tweet** (or first if you prefer):
`#GitHubActions #CICD #Claude #Copilot #AI #CodeReview #Python`

**Mentions (only if relevant accounts engage with similar tools):**
- `@github` (Marketplace)
- `@anthropicAI` (since Claude is in the description)
