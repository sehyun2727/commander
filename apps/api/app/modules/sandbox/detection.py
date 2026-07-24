"""Which template-defined checks apply to a mission's landed files
(Sprint 6 Phase 2).

Pure and synchronous -- takes a flat path list (from
`WorkspaceManager.list_tree`) and decides which `CheckSpec`s match, with
no I/O of its own, so it's trivially unit-testable without a workspace or
Docker. Detection only ever decides *whether* a trusted, template-sourced
command runs -- never what the command is (see core/interfaces/sandbox.py).
"""

from __future__ import annotations

import re

from ...core.interfaces.sandbox import CheckSpec


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate the small, trusted subset of glob syntax used by
    `CheckSpec.detect_globs` ('**/' matches any number of leading path
    segments, including none -- so 'test_add.py' at the workspace root still
    matches '**/test_*.py'; '*' matches any run of non-'/' characters) into
    a compiled regex. Not a general glob implementation -- only what the
    template actually uses."""
    placeholder = "\0"
    tokens = re.split(r"(\0|\*\*|\*)", pattern.replace("**/", placeholder))
    parts = []
    for token in tokens:
        if token == placeholder:
            parts.append("(?:.*/)?")
        elif token == "**":
            parts.append(".*")
        elif token == "*":
            parts.append("[^/]*")
        else:
            parts.append(re.escape(token))
    return re.compile(f"^{''.join(parts)}$")


def detect_checks(paths: list[str], checks: tuple[CheckSpec, ...]) -> list[CheckSpec]:
    """Every `CheckSpec` with at least one `detect_globs` pattern matching
    at least one path, in template order."""
    matched: list[CheckSpec] = []
    for check in checks:
        patterns = [_glob_to_regex(glob) for glob in check.detect_globs]
        if any(pattern.match(path) for path in paths for pattern in patterns):
            matched.append(check)
    return matched
