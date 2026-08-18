"""Sprint 15 Phase 1 §11: CEO Workspace preference persistence, defensive
normalization, and strict update validation -- exercised directly against
`app.modules.workspace_widgets.service` (no HTTP layer, no ownership
check -- that's `test_workspace_widgets_api.py`'s job), the same "test the
pure/service layer in isolation" split `test_workspace_next_action.py` /
`test_workspace_overview_api.py` already establish for Sprint 13.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select

from app.core.db_models import WorkspacePreferenceORM
from app.core.errors import StaleRevisionError
from app.modules.workspace_widgets import service
from app.modules.workspace_widgets.registry import WIDGETS, WIDGETS_BY_KEY
from app.modules.workspace_widgets.schemas import WidgetPreferenceEntry
from app.modules.workspace_widgets.service import (
    DuplicateWidgetError,
    MissingWidgetError,
    RequiredWidgetHiddenError,
    UnknownWidgetError,
)

PROJECT_A = "project-a"
PROJECT_B = "project-b"


def _full_entries(overrides: dict[str, dict] | None = None) -> list[WidgetPreferenceEntry]:
    overrides = overrides or {}
    entries = []
    for widget in sorted(WIDGETS, key=lambda w: w.default_order):
        base = {
            "widget_key": widget.key,
            "visible": widget.default_visible,
            "order": widget.default_order,
            "span": widget.default_span,
        }
        base.update(overrides.get(widget.key, {}))
        entries.append(WidgetPreferenceEntry(**base))
    return entries


@pytest.mark.asyncio
async def test_default_layout_has_every_widget_visible_and_ordered(harness):
    prefs = await service.get_effective_preferences(harness.session_factory, harness.user.id, PROJECT_A)
    assert prefs.revision == 1
    assert {e.widget_key for e in prefs.widgets} == set(WIDGETS_BY_KEY.keys())
    assert all(e.visible for e in prefs.widgets)
    assert sorted(e.order for e in prefs.widgets) == list(range(len(WIDGETS)))


@pytest.mark.asyncio
async def test_get_effective_preferences_is_idempotent_no_duplicate_rows(harness):
    await service.get_effective_preferences(harness.session_factory, harness.user.id, PROJECT_A)
    await service.get_effective_preferences(harness.session_factory, harness.user.id, PROJECT_A)
    async with harness.session_factory() as session:
        rows = (
            await session.execute(
                select(WorkspacePreferenceORM).where(
                    WorkspacePreferenceORM.user_id == harness.user.id, WorkspacePreferenceORM.project_id == PROJECT_A
                )
            )
        ).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_malformed_stored_entries_normalize_safely(harness):
    async with harness.session_factory() as session:
        row = WorkspacePreferenceORM(
            user_id=harness.user.id,
            project_id=PROJECT_A,
            schema_version=1,
            revision=1,
            widgets=[
                {"widget_key": "current_focus", "visible": True, "order": 0, "span": "half"},
                {"widget_key": "current_focus", "visible": True, "order": 1, "span": "half"},  # duplicate
                {"widget_key": "some_retired_widget", "visible": True, "order": 2, "span": "half"},  # unknown
                {"widget_key": "connection_status", "visible": False, "order": 3, "span": "not-a-span"},  # required+bad span
            ],
        )
        session.add(row)
        await session.commit()

    prefs = await service.get_effective_preferences(harness.session_factory, harness.user.id, PROJECT_A)
    keys = [e.widget_key for e in prefs.widgets]
    assert keys.count("current_focus") == 1
    assert "some_retired_widget" not in keys
    assert set(keys) == set(WIDGETS_BY_KEY.keys())  # missing widgets added back
    connection = next(e for e in prefs.widgets if e.widget_key == "connection_status")
    assert connection.visible is True  # required widget forced visible
    assert connection.span == "full"  # invalid span reset to registry default
    assert prefs.revision == 2  # normalization persisted as a real change


@pytest.mark.asyncio
async def test_required_widget_hidden_in_storage_is_restored(harness):
    async with harness.session_factory() as session:
        widgets = [
            {"widget_key": w.key, "visible": w.default_visible, "order": w.default_order, "span": w.default_span}
            for w in WIDGETS
        ]
        for entry in widgets:
            if entry["widget_key"] == "primary_next_action":
                entry["visible"] = False
        row = WorkspacePreferenceORM(
            user_id=harness.user.id, project_id=PROJECT_A, schema_version=1, revision=1, widgets=widgets
        )
        session.add(row)
        await session.commit()

    prefs = await service.get_effective_preferences(harness.session_factory, harness.user.id, PROJECT_A)
    primary = next(e for e in prefs.widgets if e.widget_key == "primary_next_action")
    assert primary.visible is True


@pytest.mark.asyncio
async def test_stored_entries_missing_a_widget_get_it_added_back(harness):
    async with harness.session_factory() as session:
        widgets = [
            {"widget_key": w.key, "visible": w.default_visible, "order": w.default_order, "span": w.default_span}
            for w in WIDGETS
            if w.key != "recent_activity"
        ]
        row = WorkspacePreferenceORM(
            user_id=harness.user.id, project_id=PROJECT_A, schema_version=1, revision=1, widgets=widgets
        )
        session.add(row)
        await session.commit()

    prefs = await service.get_effective_preferences(harness.session_factory, harness.user.id, PROJECT_A)
    assert "recent_activity" in {e.widget_key for e in prefs.widgets}


@pytest.mark.asyncio
async def test_valid_update_bumps_revision_and_persists(harness):
    initial = await service.get_effective_preferences(harness.session_factory, harness.user.id, PROJECT_A)
    entries = _full_entries({"current_focus": {"visible": False}})

    updated = await service.update_preferences(
        harness.session_factory, harness.user.id, PROJECT_A, initial.revision, entries
    )
    assert updated.revision == initial.revision + 1
    focus = next(e for e in updated.widgets if e.widget_key == "current_focus")
    assert focus.visible is False

    reread = await service.get_effective_preferences(harness.session_factory, harness.user.id, PROJECT_A)
    assert reread.revision == updated.revision
    assert not next(e for e in reread.widgets if e.widget_key == "current_focus").visible


@pytest.mark.asyncio
async def test_stale_revision_conflict_is_rejected(harness):
    initial = await service.get_effective_preferences(harness.session_factory, harness.user.id, PROJECT_A)
    entries = _full_entries()

    with pytest.raises(StaleRevisionError) as excinfo:
        await service.update_preferences(
            harness.session_factory, harness.user.id, PROJECT_A, initial.revision + 99, entries
        )
    assert excinfo.value.current_revision == initial.revision


@pytest.mark.asyncio
async def test_update_rejects_duplicate_widget_key(harness):
    entries = _full_entries()
    entries.append(entries[0])
    with pytest.raises(DuplicateWidgetError):
        await service.update_preferences(harness.session_factory, harness.user.id, PROJECT_A, 0, entries)


@pytest.mark.asyncio
async def test_update_rejects_unknown_widget_key(harness):
    entries = _full_entries()[:-1]
    entries.append(WidgetPreferenceEntry(widget_key="not_a_real_widget", visible=True, order=99, span="half"))
    with pytest.raises(UnknownWidgetError):
        await service.update_preferences(harness.session_factory, harness.user.id, PROJECT_A, 0, entries)


@pytest.mark.asyncio
async def test_update_rejects_missing_widget(harness):
    entries = _full_entries()[:-1]
    with pytest.raises(MissingWidgetError):
        await service.update_preferences(harness.session_factory, harness.user.id, PROJECT_A, 0, entries)


@pytest.mark.asyncio
async def test_update_rejects_required_widget_hidden(harness):
    entries = _full_entries({"connection_status": {"visible": False}})
    with pytest.raises(RequiredWidgetHiddenError):
        await service.update_preferences(harness.session_factory, harness.user.id, PROJECT_A, 0, entries)


@pytest.mark.asyncio
async def test_reset_restores_default_layout(harness):
    initial = await service.get_effective_preferences(harness.session_factory, harness.user.id, PROJECT_A)
    await service.update_preferences(
        harness.session_factory, harness.user.id, PROJECT_A, initial.revision, _full_entries({"current_focus": {"visible": False}})
    )

    reset = await service.reset_preferences(harness.session_factory, harness.user.id, PROJECT_A)
    assert all(e.visible for e in reset.widgets)
    assert sorted(e.order for e in reset.widgets) == list(range(len(WIDGETS)))


@pytest.mark.asyncio
async def test_preferences_are_isolated_per_project_for_same_user(harness):
    a = await service.get_effective_preferences(harness.session_factory, harness.user.id, PROJECT_A)
    await service.update_preferences(
        harness.session_factory, harness.user.id, PROJECT_A, a.revision, _full_entries({"current_focus": {"visible": False}})
    )
    b = await service.get_effective_preferences(harness.session_factory, harness.user.id, PROJECT_B)
    assert next(e for e in b.widgets if e.widget_key == "current_focus").visible is True


@pytest.mark.asyncio
async def test_preferences_are_isolated_per_user_for_same_project(harness):
    from app.modules.auth import service as auth_service

    other_user = await auth_service.register(
        harness.session_factory, "other-widgets-ceo@test.local", "otherpassword1", "Other CEO"
    )

    a = await service.get_effective_preferences(harness.session_factory, harness.user.id, PROJECT_A)
    await service.update_preferences(
        harness.session_factory, harness.user.id, PROJECT_A, a.revision, _full_entries({"current_focus": {"visible": False}})
    )
    b = await service.get_effective_preferences(harness.session_factory, other_user.id, PROJECT_A)
    assert next(e for e in b.widgets if e.widget_key == "current_focus").visible is True


@pytest.mark.asyncio
async def test_concurrent_first_creation_yields_exactly_one_row(harness):
    results = await asyncio.gather(
        *[
            service.get_effective_preferences(harness.session_factory, harness.user.id, PROJECT_A)
            for _ in range(5)
        ]
    )
    assert all(r.revision >= 1 for r in results)

    async with harness.session_factory() as session:
        rows = (
            await session.execute(
                select(WorkspacePreferenceORM).where(
                    WorkspacePreferenceORM.user_id == harness.user.id, WorkspacePreferenceORM.project_id == PROJECT_A
                )
            )
        ).scalars().all()
    assert len(rows) == 1
