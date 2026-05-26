"""Sticky PR comment poster.

Idempotently posts (or updates) a single agent-guard comment on a pull request,
identified by the ``<!-- agent-guard -->`` HTML marker at the top of the body.
Uses only the Python stdlib so we don't pull in another HTTP dependency.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

API_BASE = "https://api.github.com"
STICKY_MARKER = "<!-- agent-guard -->"


@dataclass
class GitHubContext:
    repo: str  # "owner/name"
    pr_number: int
    token: str

    @classmethod
    def from_env(cls) -> GitHubContext | None:
        repo = os.environ.get("GITHUB_REPOSITORY")
        token = os.environ.get("GITHUB_TOKEN")
        pr_ref = os.environ.get("GITHUB_REF", "")
        pr_number = _extract_pr_number(pr_ref) or _extract_pr_from_event()
        if not (repo and token and pr_number):
            return None
        return cls(repo=repo, pr_number=pr_number, token=token)


def _extract_pr_number(ref: str) -> int | None:
    # refs/pull/123/merge → 123
    parts = ref.split("/")
    if len(parts) >= 3 and parts[1] == "pull":
        try:
            return int(parts[2])
        except ValueError:
            return None
    return None


def _extract_pr_from_event() -> int | None:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path or not os.path.exists(event_path):
        return None
    try:
        with open(event_path) as f:
            event = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(event, dict):
        pr = event.get("pull_request")
        if isinstance(pr, dict):
            number = pr.get("number")
            if isinstance(number, int):
                return number
        top_number = event.get("number")
        if isinstance(top_number, int):
            return top_number
    return None


def _request(method: str, url: str, token: str, payload: dict[str, Any] | None = None) -> Any:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "agent-guard")
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = resp.read().decode()
        return json.loads(body) if body else {}


def post_sticky_comment(body: str, ctx: GitHubContext | None = None) -> str:
    """Create or update the agent-guard PR comment. Returns the comment URL."""
    ctx = ctx or GitHubContext.from_env()
    if ctx is None:
        raise RuntimeError("GitHub context not available; set GITHUB_REPOSITORY, GITHUB_TOKEN, and PR ref")
    if STICKY_MARKER not in body:
        body = f"{STICKY_MARKER}\n{body}"

    existing = _find_existing_comment(ctx)
    if existing is not None:
        url = f"{API_BASE}/repos/{ctx.repo}/issues/comments/{existing}"
        resp = _request("PATCH", url, ctx.token, {"body": body})
    else:
        url = f"{API_BASE}/repos/{ctx.repo}/issues/{ctx.pr_number}/comments"
        resp = _request("POST", url, ctx.token, {"body": body})
    return str(resp.get("html_url", ""))


def _find_existing_comment(ctx: GitHubContext) -> int | None:
    page = 1
    while True:
        url = f"{API_BASE}/repos/{ctx.repo}/issues/{ctx.pr_number}/comments?per_page=100&page={page}"
        try:
            data = _request("GET", url, ctx.token)
        except urllib.error.HTTPError:
            return None
        if not isinstance(data, list) or not data:
            return None
        for comment in data:
            if STICKY_MARKER in (comment.get("body") or ""):
                cid = comment.get("id")
                return int(cid) if isinstance(cid, int) else None
        if len(data) < 100:
            return None
        page += 1
