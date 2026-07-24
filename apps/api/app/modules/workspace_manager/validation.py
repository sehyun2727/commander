"""Write-safety validation for workspace file writes (Sprint 5 hard
requirements): every path must be relative and stay inside the repo after
normalization, and every file must be small, text-only content.
Violations are reported back to the caller as a skip reason -- they never
raise, so one bad file in an attempt doesn't lose the good ones.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

MAX_FILES_PER_ATTEMPT = 30
MAX_FILE_BYTES = 256 * 1024


def validate_path(repo_root: Path, path: str) -> tuple[Path | None, str | None]:
    """Returns (resolved_absolute_path, None) if path is safe to write, or
    (None, reason) if not. repo_root must already be an absolute, resolved
    path."""
    if not path or not path.strip():
        return None, "empty path"
    normalized = PurePosixPath(path.replace("\\", "/"))
    if normalized.is_absolute():
        return None, "absolute paths are not allowed"
    if ".." in normalized.parts:
        return None, "path traversal ('..') is not allowed"
    if normalized.parts and normalized.parts[0] == ".git":
        return None, "writes to .git/ are not allowed"
    candidate = (repo_root / str(normalized)).resolve()
    try:
        candidate.relative_to(repo_root)
    except ValueError:
        return None, "path escapes the workspace"
    return candidate, None


def validate_content(content: str) -> str | None:
    """Returns a skip reason if content is invalid, else None."""
    if "\0" in content:
        return "binary content (NUL byte) is not allowed"
    size = len(content.encode("utf-8"))
    if size > MAX_FILE_BYTES:
        return f"exceeds {MAX_FILE_BYTES // 1024}KB limit ({size} bytes)"
    return None
