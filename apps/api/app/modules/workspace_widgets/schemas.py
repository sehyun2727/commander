"""Sprint 15: public, typed CEO Workspace preference schemas.

`WorkspacePreferences` is always a normalized, authoritative representation
-- every field has already passed through `service.normalize()` before it
reaches a response model, so a client never has to guess whether a value
is "raw" or "safe" (§4.6/§5). `revision` is the optimistic-concurrency
token (DECISIONS.md #228): a client must echo the `revision` it last read
as `expected_revision` on update, or receive a structured 409.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .registry import MAX_WIDGET_ENTRIES

SCHEMA_VERSION = 1


class WidgetDefinitionResponse(BaseModel):
    key: str
    title: str
    description: str
    category: str
    required: bool
    default_visible: bool
    default_order: int
    default_span: Literal["full", "half"]


class WidgetPreferenceEntry(BaseModel):
    widget_key: str
    visible: bool
    order: int = Field(ge=0)
    span: Literal["full", "half"]


class WorkspacePreferences(BaseModel):
    schema_version: int
    revision: int
    widgets: list[WidgetPreferenceEntry] = Field(max_length=MAX_WIDGET_ENTRIES)
    updated_at: datetime


class WorkspacePreferencesUpdateRequest(BaseModel):
    expected_revision: int
    widgets: list[WidgetPreferenceEntry] = Field(max_length=MAX_WIDGET_ENTRIES)
