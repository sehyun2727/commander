"""Sprint 18 §5 -- Pydantic shapes for Project Memory: the stored-record
shape, the PM's optional recall request, and one recalled result item.

`RecallRequest` is deliberately lenient: it is parsed from untrusted,
free-form PM JSON output (same spirit as `planning/orchestrator.py`'s
permissive `_VALIDATORS`), so malformed field *values* are coerced away
rather than raising and aborting the planning turn (sprint-18.md §4.10).
Every cap here is advisory for the caller -- `memory.service.recall`
re-applies the server-enforced ceilings in `registry.py` regardless of
what this object holds.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from .registry import (
    CATEGORIES,
    MAX_KEYWORD_COUNT,
    MAX_KEYWORD_LENGTH,
    MAX_RECALL_LIMIT,
    MAX_RECALL_LOOKBACK_DAYS,
    MAX_TAG_COUNT,
    MAX_TAG_LENGTH,
)


class MemoryRecord(BaseModel):
    """Full stored shape of one `memory_records` row."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    category: str
    source_event_id: str
    source_task_id: str | None = None
    source_specification_id: str | None = None
    title: str
    content_json: dict
    tags: list[str]
    keywords_text: str
    created_at: datetime


def _coerce_str_list(v: object, *, max_count: int, max_length: int) -> list[str]:
    if not isinstance(v, list):
        return []
    out: list[str] = []
    for item in v:
        if not isinstance(item, str):
            continue
        cleaned = item.strip().lower()
        if not cleaned:
            continue
        out.append(cleaned[:max_length])
        if len(out) >= max_count:
            break
    return out


class RecallRequest(BaseModel):
    """Parsed from the PM's optional `recall_request` planning JSON field
    (sprint-18.md §4.8). `categories=None`/absent means "search all six";
    `categories=[]` explicitly means "search none" (§4.11) -- that
    distinction survives coercion below."""

    model_config = ConfigDict(extra="ignore")

    categories: list[str] | None = None
    tags: list[str] = []
    keywords: list[str] = []
    since_days: int | None = None
    limit: int = MAX_RECALL_LIMIT

    @field_validator("categories", mode="before")
    @classmethod
    def _coerce_categories(cls, v: object) -> list[str] | None:
        if v is None:
            return None
        if not isinstance(v, list):
            return None
        return [c for c in v if isinstance(c, str) and c in CATEGORIES]

    @field_validator("tags", mode="before")
    @classmethod
    def _coerce_tags(cls, v: object) -> list[str]:
        return _coerce_str_list(v, max_count=MAX_TAG_COUNT, max_length=MAX_TAG_LENGTH)

    @field_validator("keywords", mode="before")
    @classmethod
    def _coerce_keywords(cls, v: object) -> list[str]:
        return _coerce_str_list(v, max_count=MAX_KEYWORD_COUNT, max_length=MAX_KEYWORD_LENGTH)

    @field_validator("since_days", mode="before")
    @classmethod
    def _coerce_since_days(cls, v: object) -> int | None:
        if v is None:
            return None
        try:
            days = int(v)
        except (TypeError, ValueError):
            return None
        return max(0, min(days, MAX_RECALL_LOOKBACK_DAYS))

    @field_validator("limit", mode="before")
    @classmethod
    def _coerce_limit(cls, v: object) -> int:
        if v is None:
            return MAX_RECALL_LIMIT
        try:
            n = int(v)
        except (TypeError, ValueError):
            return MAX_RECALL_LIMIT
        return max(1, min(n, MAX_RECALL_LIMIT))


class RecalledMemory(BaseModel):
    """One ranked recall result -- bounded, no raw `content_json` echo."""

    id: str
    category: str
    title: str
    tags: list[str]
    created_at: datetime
    preview: str
