"""Detect Python imports that can't be resolved against stdlib, declared deps, or local modules.

This is the M1 hallucination detector. It only handles Python; other ecosystems
arrive in M2 with tree-sitter.
"""

from __future__ import annotations

import ast
import re
import sys
from collections.abc import Iterable
from pathlib import Path

from agent_guard.analyzers.base import Analyzer, Context
from agent_guard.models import FileChange, Finding, Severity

# Common third-party packages whose import name differs from the distribution name.
# Used as a hint so we don't falsely flag `cv2` when `opencv-python` is declared.
_IMPORT_ALIASES = {
    "cv2": "opencv-python",
    "PIL": "pillow",
    "skimage": "scikit-image",
    "sklearn": "scikit-learn",
    "yaml": "pyyaml",
    "bs4": "beautifulsoup4",
    "OpenSSL": "pyopenssl",
    "Crypto": "pycryptodome",
    "google": "google-api-python-client",
    "dateutil": "python-dateutil",
    "dotenv": "python-dotenv",
    "magic": "python-magic",
    "jose": "python-jose",
}

_PYPROJECT_NAME_RE = re.compile(r"^\s*([A-Za-z0-9_.\-]+)", re.MULTILINE)


def _stdlib_modules() -> frozenset[str]:
    # Python 3.10+ exposes sys.stdlib_module_names.
    names = getattr(sys, "stdlib_module_names", None)
    return frozenset(names) if names else frozenset()


_STDLIB = _stdlib_modules()


def _normalize(name: str) -> str:
    return name.lower().replace("_", "-")


def _parse_requirements_txt(text: str) -> set[str]:
    out: set[str] = set()
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        # Strip version specifiers, extras, env markers.
        name = re.split(r"[<>=!~;\[]", line, maxsplit=1)[0].strip()
        if name:
            out.add(_normalize(name))
    return out


def _parse_pyproject(text: str) -> set[str]:
    # Cheap regex parse: pull names from `dependencies = [...]` and `[project.optional-dependencies]`.
    out: set[str] = set()
    # PEP 621 dependencies
    for m in re.finditer(r"""dependencies\s*=\s*\[(.*?)\]""", text, re.DOTALL):
        for line in m.group(1).splitlines():
            line = line.strip().strip(",").strip('"').strip("'")
            if not line:
                continue
            name = re.split(r"[<>=!~;\[]", line, maxsplit=1)[0].strip()
            if name:
                out.add(_normalize(name))
    # Poetry-style [tool.poetry.dependencies]
    for m in re.finditer(r"\[tool\.poetry\.(?:dev-)?dependencies\](.*?)(?=^\[|\Z)", text, re.DOTALL | re.MULTILINE):
        for line in m.group(1).splitlines():
            mm = _PYPROJECT_NAME_RE.match(line)
            if mm:
                name = mm.group(1)
                if name.lower() != "python":
                    out.add(_normalize(name))
    return out


def _collect_declared_deps(repo_root: Path) -> set[str]:
    deps: set[str] = set()
    for fname in ("requirements.txt", "requirements-dev.txt", "requirements/base.txt"):
        p = repo_root / fname
        if p.is_file():
            deps |= _parse_requirements_txt(p.read_text(errors="replace"))
    pyproject = repo_root / "pyproject.toml"
    if pyproject.is_file():
        deps |= _parse_pyproject(pyproject.read_text(errors="replace"))
    return deps


def _collect_local_modules(repo_root: Path) -> set[str]:
    """Top-level package/module names that exist in the repo."""
    modules: set[str] = set()
    for root in (repo_root, repo_root / "src"):
        if not root.is_dir():
            continue
        try:
            entries = list(root.iterdir())
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.is_dir() and (entry / "__init__.py").is_file():
                    modules.add(entry.name)
                elif root is repo_root and entry.is_file() and entry.suffix == ".py":
                    modules.add(entry.stem)
            except OSError:
                continue
    return modules


def _imports_from_source(source: str) -> set[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def _imports_from_added_lines(change: FileChange) -> set[str]:
    """Fallback when we don't have the full file: parse only the added lines that look like imports."""
    snippet_lines = [content for _, content in change.added_lines if content.lstrip().startswith(("import ", "from "))]
    if not snippet_lines:
        return set()
    return _imports_from_source("\n".join(snippet_lines))


class HallucinatedImportScanner(Analyzer):
    id = "hallucinated_imports"
    category = "hallucination"
    languages = ("python",)

    def analyze(self, ctx: Context) -> Iterable[Finding]:
        declared = _collect_declared_deps(ctx.repo_root)
        local = _collect_local_modules(ctx.repo_root)

        for change in ctx.changes:
            if not change.is_python or change.status == "deleted":
                continue

            if change.full_added_content:
                all_imports = _imports_from_source(change.full_added_content)
                # Restrict to imports likely *introduced* in this diff.
                added_text = change.added_text()
                introduced = {n for n in all_imports if re.search(rf"(?m)^\s*(?:from\s+{re.escape(n)}\b|import\s+{re.escape(n)}\b)", added_text)}
            else:
                introduced = _imports_from_added_lines(change)

            for name in sorted(introduced):
                if self._is_resolvable(name, declared, local):
                    continue
                line_no = self._first_import_line(change, name)
                yield Finding(
                    rule_id="hallucination.unresolved-import",
                    severity=Severity.HIGH,
                    file=change.path,
                    line=line_no,
                    message=f"Import `{name}` is not in stdlib, declared dependencies, or local modules — possible hallucination",
                    evidence=f"import {name}",
                    category="hallucination",
                    metadata={"module": name, "alias_hint": _IMPORT_ALIASES.get(name)},
                )

    @staticmethod
    def _is_resolvable(name: str, declared: set[str], local: set[str]) -> bool:
        if name in _STDLIB:
            return True
        if name in local:
            return True
        norm = _normalize(name)
        if norm in declared:
            return True
        # Resolve via known import→distribution alias map.
        alias = _IMPORT_ALIASES.get(name)
        return bool(alias and _normalize(alias) in declared)

    @staticmethod
    def _first_import_line(change: FileChange, name: str) -> int:
        for line_no, content in change.added_lines:
            stripped = content.lstrip()
            if stripped.startswith(f"import {name}") or stripped.startswith(f"from {name}"):
                return line_no
        return change.added_lines[0][0] if change.added_lines else 1
