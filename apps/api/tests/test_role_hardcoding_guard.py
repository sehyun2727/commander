"""Sprint 10 Phase 4 §17: an automated check for CLAUDE.md Rule #16
("Roles are data; Employees are instances") that isn't a naive substring
search. A substring search (`assert "engineer" not in source`) produces
false positives against comments, docstrings, fixtures, log messages, and
test descriptions -- this walks the actual AST instead, so it only flags
code shapes that are structurally a role-identity branch or a
position-based access, wherever they occur in the source text.

Live role keys are read from the real `TEMPLATE` (not a literal list in
this file), so the guard automatically covers any Role the template adds
later without needing an update here.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.templates import TEMPLATE

APP_ROOT = Path(__file__).resolve().parent.parent / "app"

# `app/templates/` is the one place Rule #16 explicitly permits role-name
# constants -- it's the template *assembling its own data* (RoleSpec field
# values), not a consumer branching on role identity.
EXCLUDED_DIRS = {APP_ROOT / "templates"}

ROLE_KEYS = frozenset(TEMPLATE.roles_by_key.keys())


def _iter_scanned_files() -> list[Path]:
    files = []
    for path in APP_ROOT.rglob("*.py"):
        if any(excluded in path.parents for excluded in EXCLUDED_DIRS):
            continue
        files.append(path)
    return files


def _is_role_key_constant(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in ROLE_KEYS


def _looks_like_a_roles_collection(node: ast.expr) -> bool:
    """Heuristic for the *object* being subscripted in a position-based
    access, e.g. `TEMPLATE.roles[0]` or `ROLES[1]` -- matches on the
    trailing identifier so it survives however the collection is reached
    (attribute chain, bare name, etc.)."""
    name = ""
    if isinstance(node, ast.Attribute):
        name = node.attr
    elif isinstance(node, ast.Name):
        name = node.id
    return name.lower() in {"roles", "role_specs"}


class _Violation:
    def __init__(self, path: Path, node: ast.AST, kind: str, detail: str):
        self.path = path
        self.line = node.lineno
        self.kind = kind
        self.detail = detail

    def __str__(self) -> str:
        rel = self.path.relative_to(APP_ROOT.parent)
        return f"{rel}:{self.line}: [{self.kind}] {self.detail}"


def _check_compare(node: ast.Compare, path: Path) -> _Violation | None:
    operands = [node.left, *node.comparators]

    for op in node.ops:
        if isinstance(op, (ast.Eq, ast.NotEq)):
            for operand in operands:
                if _is_role_key_constant(operand):
                    return _Violation(
                        path, node, "role-specific behavioral branch",
                        f"compares against role key {operand.value!r} directly instead of RoleSpec/StageSpec data",
                    )
        if isinstance(op, (ast.In, ast.NotIn)):
            for operand in operands:
                if isinstance(operand, (ast.List, ast.Tuple, ast.Set)):
                    literal_role_keys = [elt.value for elt in operand.elts if _is_role_key_constant(elt)]
                    if literal_role_keys:
                        return _Violation(
                            path, node, "role-specific behavioral branch",
                            f"membership test against a hardcoded role-key literal set {literal_role_keys!r}",
                        )
    return None


def _check_subscript(node: ast.Subscript, path: Path) -> _Violation | None:
    index = node.slice
    if isinstance(index, ast.Constant) and isinstance(index.value, int) and _looks_like_a_roles_collection(node.value):
        return _Violation(
            path, node, "position-based access",
            f"indexes a roles collection by position ([{index.value}]) instead of by role_key or stage kind",
        )
    if isinstance(index, ast.Constant) and isinstance(index.value, str) and index.value in ROLE_KEYS:
        return _Violation(
            path, node, "hardcoded role dependency",
            f"subscripts a mapping with the literal role key {index.value!r} instead of a resolved role_key variable",
        )
    return None


def _scan(path: Path) -> list[_Violation]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    violations: list[_Violation] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            violation = _check_compare(node, path)
        elif isinstance(node, ast.Subscript):
            violation = _check_subscript(node, path)
        else:
            violation = None
        if violation:
            violations.append(violation)
    return violations


def test_no_hardcoded_role_identity_branches_outside_the_template():
    """Rule #16: no engine/prompt/module code may branch on, or index by
    position into, a specific Role's identity. `app/templates/` is the only
    permitted exception (it *is* the role data)."""
    all_violations: list[_Violation] = []
    for path in _iter_scanned_files():
        all_violations.extend(_scan(path))

    assert not all_violations, "Rule #16 violations found:\n" + "\n".join(str(v) for v in all_violations)


def test_the_guard_actually_detects_a_real_violation():
    """A guard that never fires is worthless -- prove the AST walk actually
    catches the exact forbidden patterns CLAUDE.md Rule #16 names, using
    inline source instead of scanning real files."""
    behavioral_branch = ast.parse('if role_key == "engineer":\n    pass\n')
    membership_branch = ast.parse('if role in ("pm", "reviewer"):\n    pass\n')
    positional_access = ast.parse("first = TEMPLATE.roles[0]\n")
    subscript_dependency = ast.parse('agent = agents_by_role["pm"]\n')

    fake_path = APP_ROOT / "modules" / "_fixture.py"
    for tree in (behavioral_branch, membership_branch, positional_access, subscript_dependency):
        found = [v for node in ast.walk(tree) for v in [_check_compare(node, fake_path) if isinstance(node, ast.Compare) else _check_subscript(node, fake_path) if isinstance(node, ast.Subscript) else None] if v]
        assert found, ast.dump(tree)


@pytest.mark.parametrize("role_key", sorted(ROLE_KEYS))
def test_role_keys_used_by_the_guard_are_real(role_key: str):
    """Sanity check that ROLE_KEYS was actually populated from the live
    template and isn't silently empty (which would make the main guard
    test vacuously pass no matter what)."""
    assert role_key in TEMPLATE.roles_by_key
