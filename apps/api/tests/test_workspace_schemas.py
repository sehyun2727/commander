"""Sprint 13 Phase 1: pure schema-level tests for the CEO Workspace public
contract (`app/modules/workspace_overview/schemas.py`). No database, no
event loop -- these are plain Pydantic model checks that the public
snapshot never exposes an unsafe field and that `event_cursor` behaves as
the plain `EventORM.seq` integer decided in docs/DECISIONS.md #217 (no new
cursor encoding, so "round trip" is just int in / int out).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import BaseModel, ValidationError

from app.modules.workspace_overview.schemas import (
    ActivityItem,
    EmployeeCounts,
    Focus,
    MissionSummary,
    NextAction,
    OrganizationSummary,
    PendingActions,
    PlanningSummary,
    ProjectSummary,
    WorkspaceSnapshot,
)

_FORBIDDEN_FIELD_NAMES = {
    "payload",
    "system_prompt",
    "prompt",
    "api_key",
    "secret",
    "secret_value",
    "credential",
    "raw_response",
    "chain_of_thought",
}

_NOW = datetime.now(timezone.utc)


def _project() -> ProjectSummary:
    return ProjectSummary(id="proj-1", name="Acme AI", provider="mock", archived=False, created_at=_NOW)


def _snapshot(event_cursor: int) -> WorkspaceSnapshot:
    return WorkspaceSnapshot(
        schema_version=1,
        generated_at=_NOW,
        project=_project(),
        organization=OrganizationSummary(
            leadership=[], counts=EmployeeCounts(total=0, busy=0, idle=0, error=0), employees=[]
        ),
        focus=Focus(resource_type=None, resource_id=None, status=None),
        pending_actions=PendingActions(),
        next_action=NextAction(
            kind="no_action",
            title="Nothing needs your attention",
            explanation="Everything is quiet right now.",
            target_resource_type=None,
            target_resource_id=None,
            route=None,
            urgency="low",
            requires_ceo_input=False,
        ),
        planning=PlanningSummary(
            active=False, specification_id=None, status=None, current_version=None, turn_count=None,
            unresolved_questions=0,
        ),
        missions=MissionSummary(active=[], recent=[]),
        recent_activity=[],
        event_cursor=event_cursor,
    )


def test_activity_item_field_allowlist_excludes_forbidden_fields():
    fields = set(ActivityItem.model_fields.keys())
    assert fields == {"id", "seq", "type", "kind", "actor_role", "actor_name", "reason", "created_at"}
    assert fields.isdisjoint(_FORBIDDEN_FIELD_NAMES)


def test_workspace_snapshot_never_declares_a_forbidden_field_anywhere_in_the_tree():
    def _walk(model_cls) -> set[str]:
        names: set[str] = set()
        for field_name, field_info in model_cls.model_fields.items():
            names.add(field_name)
            annotation = field_info.annotation
            for candidate in getattr(annotation, "__args__", (annotation,)):
                if isinstance(candidate, type) and issubclass(candidate, BaseModel):
                    names |= _walk(candidate)
        return names

    all_field_names = _walk(WorkspaceSnapshot)
    assert all_field_names.isdisjoint(_FORBIDDEN_FIELD_NAMES)


def test_event_cursor_round_trips_as_plain_int():
    snapshot = _snapshot(event_cursor=42)
    dumped = snapshot.model_dump()
    assert dumped["event_cursor"] == 42
    restored = WorkspaceSnapshot.model_validate(dumped)
    assert restored.event_cursor == 42
    assert isinstance(restored.event_cursor, int)


def test_event_cursor_zero_is_valid_for_a_project_with_no_events_yet():
    snapshot = _snapshot(event_cursor=0)
    assert snapshot.event_cursor == 0


def test_malformed_event_cursor_is_rejected_by_the_schema():
    dumped = _snapshot(event_cursor=0).model_dump()
    dumped["event_cursor"] = "not-a-cursor"
    with pytest.raises(ValidationError):
        WorkspaceSnapshot.model_validate(dumped)
