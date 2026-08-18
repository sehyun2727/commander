"""Output bounding for Agent Harness tool results (Sprint 16 §4.10,
DECISIONS.md #233, Rule #7).

Tool output (file content, search matches, diffs, sandboxed command
stdout/stderr) is untrusted and unbounded in principle -- a single tool
call must never be allowed to blow up context size or leak more than a
bounded window of repository content back through the provider. Mirrors
`LocalGitWorkspaceManager.diff`'s existing `(text, truncated: bool)`
truncation convention rather than inventing a new shape.
"""

from __future__ import annotations

from ...core.config import settings

_REDACTED_ENV_KEYS = ("ANTHROPIC_API_KEY", "DATABASE_URL", "SECRET", "TOKEN", "PASSWORD", "KEY")


def bound_output(text: str, *, max_bytes: int | None = None) -> tuple[str, bool]:
    """Truncate `text` to at most `max_bytes` UTF-8 bytes, returning
    `(text, truncated)`. Defaults to `settings.commander_harness_max_output_bytes`."""
    limit = max_bytes if max_bytes is not None else settings.commander_harness_max_output_bytes
    encoded = text.encode("utf-8")
    if len(encoded) <= limit:
        return text, False
    return encoded[:limit].decode("utf-8", errors="ignore"), True


def redact_environment_like_content(text: str) -> str:
    """Best-effort redaction for accidental secret-shaped lines in tool
    output (e.g. a stray `.env` line matched by a search). This is
    defense-in-depth, not the primary control -- the primary control is
    that `SecretsProvider` values are never written into a mission
    workspace or the harness's own environment in the first place
    (Rule #7); tool handlers never read process environment variables."""
    redacted_lines: list[str] = []
    for line in text.splitlines(keepends=True):
        upper = line.upper()
        if "=" in line and any(marker in upper for marker in _REDACTED_ENV_KEYS):
            key, _, _ = line.partition("=")
            redacted_lines.append(f"{key}=[redacted]\n")
        else:
            redacted_lines.append(line)
    return "".join(redacted_lines)
