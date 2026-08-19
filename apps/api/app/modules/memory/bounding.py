"""Sprint 18 §4.4 -- local, duplicated output-bounding helpers.

The memory module may not import `agent_harness` directly (sprint-18.md
§5's forbidden-imports list, Rule #1). `bound_text` and
`redact_environment_like_content` are small, independently-owned
duplicates of `agent_harness.output.bound_output` /
`.redact_environment_like_content`, mirroring the duplicate-rather-than-
cross-import precedent already documented on
`planning/orchestrator.py._resolve_agent`.
"""

from __future__ import annotations

import json

from .registry import MAX_CONTENT_JSON_BYTES, MAX_FIELD_BYTES, MAX_KEYWORDS_TEXT_LENGTH, MAX_TAG_COUNT, MAX_TAG_LENGTH

_REDACTED_ENV_KEYS = ("ANTHROPIC_API_KEY", "DATABASE_URL", "SECRET", "TOKEN", "PASSWORD", "KEY")


def bound_text(text: str, *, max_bytes: int = MAX_FIELD_BYTES) -> str:
    """Truncate `text` to at most `max_bytes` UTF-8 bytes."""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


def redact_environment_like_content(text: str) -> str:
    """Best-effort redaction for accidental secret-shaped lines in any
    excerpt ultimately derived from tool/sandbox output (e.g. Employee
    surrender text quoting a failed command). Defense-in-depth only, same
    as the harness's own copy."""
    redacted_lines: list[str] = []
    for line in text.splitlines(keepends=True):
        upper = line.upper()
        if "=" in line and any(marker in upper for marker in _REDACTED_ENV_KEYS):
            key, _, _ = line.partition("=")
            redacted_lines.append(f"{key}=[redacted]\n")
        else:
            redacted_lines.append(line)
    return "".join(redacted_lines)


def cap_content_json(content: dict, *, max_bytes: int = MAX_CONTENT_JSON_BYTES) -> dict:
    """If `content` serializes over `max_bytes`, drop the single largest
    string-valued field and mark `_truncated: true` rather than persist an
    unbounded record (sprint-18.md §4.4)."""
    serialized = json.dumps(content, ensure_ascii=False, default=str)
    if len(serialized.encode("utf-8")) <= max_bytes:
        return content
    string_fields = [(k, v) for k, v in content.items() if isinstance(v, str) and v]
    if not string_fields:
        return content
    largest_key, _ = max(string_fields, key=lambda kv: len(kv[1]))
    trimmed = dict(content)
    trimmed[largest_key] = ""
    trimmed["_truncated"] = True
    return trimmed


def cap_tags(tags: list[str], *, max_count: int = MAX_TAG_COUNT, max_length: int = MAX_TAG_LENGTH) -> list[str]:
    """Lowercase, truncate, dedupe (first-seen order), cap count -- the
    same bound applied to a PM's `RecallRequest.tags`, applied here to the
    tags an extractor derives (sprint-18.md §4.3: `tags` column is bounded
    at insert time, not just at query time)."""
    seen: set[str] = set()
    out: list[str] = []
    for tag in tags:
        cleaned = tag.strip().lower()[:max_length]
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
        if len(out) >= max_count:
            break
    return out


def build_keywords_text(*parts: str, max_length: int = MAX_KEYWORDS_TEXT_LENGTH) -> str:
    """Lowercased, whitespace-normalized concatenation of salient text
    fields for `keywords_text` substring search (sprint-18.md §4.5)."""
    normalized = " ".join(" ".join(part.split()) for part in parts if part)
    return normalized.lower()[:max_length]
