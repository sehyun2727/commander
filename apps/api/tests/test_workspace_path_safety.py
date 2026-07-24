from __future__ import annotations

from pathlib import Path

from app.modules.workspace_manager.validation import (
    MAX_FILE_BYTES,
    validate_content,
    validate_path,
)


def _root(tmp_path: Path) -> Path:
    root = (tmp_path / "repo").resolve()
    root.mkdir()
    return root


def test_validate_path_accepts_normal_relative_path(tmp_path):
    root = _root(tmp_path)
    resolved, reason = validate_path(root, "src/app.py")
    assert reason is None
    assert resolved == (root / "src" / "app.py").resolve()


def test_validate_path_rejects_empty(tmp_path):
    root = _root(tmp_path)
    resolved, reason = validate_path(root, "")
    assert resolved is None
    assert "empty" in reason


def test_validate_path_rejects_posix_absolute(tmp_path):
    root = _root(tmp_path)
    resolved, reason = validate_path(root, "/etc/passwd")
    assert resolved is None
    assert "absolute" in reason


def test_validate_path_rejects_windows_drive_absolute(tmp_path):
    root = _root(tmp_path)
    resolved, reason = validate_path(root, "C:/Windows/evil.txt")
    assert resolved is None
    assert reason is not None


def test_validate_path_rejects_traversal(tmp_path):
    root = _root(tmp_path)
    resolved, reason = validate_path(root, "../outside.txt")
    assert resolved is None
    assert "traversal" in reason


def test_validate_path_rejects_nested_traversal(tmp_path):
    root = _root(tmp_path)
    resolved, reason = validate_path(root, "src/../../outside.txt")
    assert resolved is None
    assert "traversal" in reason


def test_validate_path_rejects_dot_git(tmp_path):
    root = _root(tmp_path)
    resolved, reason = validate_path(root, ".git/hooks/pre-commit")
    assert resolved is None
    assert ".git" in reason


def test_validate_path_normalizes_dot_component(tmp_path):
    root = _root(tmp_path)
    resolved, reason = validate_path(root, "src/./app.py")
    assert reason is None
    assert resolved == (root / "src" / "app.py").resolve()


def test_validate_content_rejects_nul_byte():
    assert validate_content("hello\x00world") is not None


def test_validate_content_accepts_normal_text():
    assert validate_content("print('hello world')\n") is None


def test_validate_content_rejects_oversized():
    reason = validate_content("a" * (MAX_FILE_BYTES + 1))
    assert reason is not None
    assert "256" in reason
