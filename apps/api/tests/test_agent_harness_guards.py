from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.core.errors import ToolPathViolationError
from app.modules.agent_harness.guards import guard_content, guard_path


def _root(tmp_path: Path) -> Path:
    root = (tmp_path / "repo").resolve()
    root.mkdir()
    return root


def test_guard_path_accepts_normal_relative_path(tmp_path):
    root = _root(tmp_path)
    resolved = guard_path("read_file", root, "src/app.py")
    assert resolved == (root / "src" / "app.py").resolve()


def test_guard_path_rejects_absolute_path(tmp_path):
    root = _root(tmp_path)
    with pytest.raises(ToolPathViolationError):
        guard_path("read_file", root, "/etc/passwd")


def test_guard_path_rejects_traversal(tmp_path):
    root = _root(tmp_path)
    with pytest.raises(ToolPathViolationError):
        guard_path("read_file", root, "../outside.txt")


def test_guard_path_rejects_dot_git(tmp_path):
    root = _root(tmp_path)
    with pytest.raises(ToolPathViolationError):
        guard_path("apply_patch", root, ".git/hooks/pre-commit")


def test_guard_path_rejects_symlink_escape(tmp_path):
    root = _root(tmp_path)
    outside = (tmp_path / "outside").resolve()
    outside.mkdir()
    (outside / "secret.txt").write_text("secret")
    link = root / "escape"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation not permitted in this environment")
    with pytest.raises(ToolPathViolationError):
        guard_path("read_file", root, "escape/secret.txt")


def test_guard_path_rejects_direct_symlink_target(tmp_path):
    root = _root(tmp_path)
    real_file = root / "real.txt"
    real_file.write_text("hello")
    link = root / "link.txt"
    try:
        link.symlink_to(real_file)
    except OSError:
        pytest.skip("symlink creation not permitted in this environment")
    with pytest.raises(ToolPathViolationError):
        guard_path("apply_patch", root, "link.txt")


def test_guard_content_accepts_normal_text():
    assert guard_content("read_file", "print('hi')\n") == "print('hi')\n"


def test_guard_content_rejects_nul_byte():
    with pytest.raises(ToolPathViolationError):
        guard_content("apply_patch", "bad\x00content")


def test_guard_content_rejects_oversized():
    with pytest.raises(ToolPathViolationError):
        guard_content("apply_patch", "a" * (256 * 1024 + 1))
