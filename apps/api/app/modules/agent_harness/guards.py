"""Workspace-root confinement guard for Agent Harness tool calls (Sprint
16 §4.5, DECISIONS.md #233).

Reuses `workspace_manager.validation.validate_path`/`validate_content`
rather than re-implementing path safety: that function already performs
genuine confinement via `Path.resolve()` + `relative_to()` (not
string-prefix matching), and `.resolve()` already follows any symlink
present in an *existing* path component, so a symlink planted inside the
workspace that points outside it is already caught by "path escapes the
workspace" there.

This module adds one check `validate_path` has no reason to make: it
rejects any tool call whose resolved target path currently *is* a
symlink, even one pointing back inside the workspace. Writing through an
internal symlink would silently mutate a different file than the one the
Employee named -- a "confused deputy" risk `validate_path` (built for the
one-shot Engineer's own not-yet-existing file writes) never had to
consider.
"""

from __future__ import annotations

from pathlib import Path

from ...core.errors import ToolPathViolationError
from ..workspace_manager.validation import validate_content, validate_path


def guard_path(tool_name: str, repo_root: Path, raw_path: str) -> Path:
    """Return the resolved, confined absolute path for `raw_path`, or raise
    `ToolPathViolationError`."""
    resolved, error = validate_path(repo_root, raw_path)
    if resolved is None or error is not None:
        raise ToolPathViolationError(tool_name, raw_path)
    if resolved.exists() and resolved.is_symlink():
        raise ToolPathViolationError(tool_name, raw_path)
    return resolved


def guard_content(tool_name: str, content: str) -> str:
    error = validate_content(content)
    if error is not None:
        raise ToolPathViolationError(tool_name, error)
    return content
