"""Unified-diff → FileChange parsing.

Wraps the `unidiff` library and (when available) reads the post-image file
content from disk so AST-based analyzers can parse the full new file rather
than just the added hunks.
"""

from __future__ import annotations

from pathlib import Path
from typing import TextIO

from unidiff import PatchSet

from agent_guard.models import FileChange, FileStatus


def _status(patched_file: object) -> FileStatus:
    # unidiff exposes is_added_file / is_removed_file / is_rename
    if getattr(patched_file, "is_added_file", False):
        return "added"
    if getattr(patched_file, "is_removed_file", False):
        return "deleted"
    if getattr(patched_file, "is_rename", False):
        return "renamed"
    return "modified"


def parse_diff(stream: TextIO, repo_root: Path | None = None) -> list[FileChange]:
    """Parse a unified diff stream into FileChange objects.

    If `repo_root` is provided, attempts to load the full post-image content
    from disk for added/modified files (used by AST analyzers).
    """
    return _parse(PatchSet(stream), repo_root)


def parse_diff_text(text: str, repo_root: Path | None = None) -> list[FileChange]:
    return _parse(PatchSet(text), repo_root)


def _parse(patchset: PatchSet, repo_root: Path | None) -> list[FileChange]:
    changes: list[FileChange] = []
    for patched in patchset:
        # unidiff prefixes paths with a/ b/; the `path` attribute strips it.
        path = patched.path
        status = _status(patched)
        if status == "deleted":
            changes.append(FileChange(path=path, status=status))
            continue

        added: list[tuple[int, str]] = []
        removed: list[tuple[int, str]] = []
        for hunk in patched:
            for line in hunk:
                if line.is_added and line.target_line_no is not None:
                    added.append((line.target_line_no, line.value.rstrip("\n")))
                elif line.is_removed and line.source_line_no is not None:
                    removed.append((line.source_line_no, line.value.rstrip("\n")))

        full_content: str | None = None
        if repo_root is not None:
            full_path = repo_root / path
            if full_path.is_file():
                try:
                    full_content = full_path.read_text(errors="replace")
                except OSError:
                    full_content = None

        changes.append(
            FileChange(
                path=path,
                status=status,
                added_lines=added,
                removed_lines=removed,
                full_added_content=full_content,
            )
        )
    return changes
