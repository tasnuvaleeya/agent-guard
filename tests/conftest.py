from __future__ import annotations

from pathlib import Path

import pytest

from agent_guard.analyzers import Context
from agent_guard.config import AgentGuardConfig


@pytest.fixture
def empty_context(tmp_path: Path) -> Context:
    return Context(repo_root=tmp_path, changes=[], config=AgentGuardConfig())


def make_diff(path: str, added: list[str], status: str = "added") -> str:
    """Build a synthetic unified-diff string for a single file."""
    body = "\n".join(f"+{line}" for line in added)
    if status == "added":
        header = f"diff --git a/{path} b/{path}\nnew file mode 100644\n--- /dev/null\n+++ b/{path}\n"
    else:
        header = f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
    hunk = f"@@ -0,0 +1,{len(added)} @@\n{body}\n"
    return header + hunk
