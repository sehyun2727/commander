"""Sprint 15 §5/§6/§8/§9: CEO Workspace preference persistence, defensive
normalization, and strict update validation.

Two different tolerance levels by design (brief §"Versioning/normalization"
vs §"Server-side validation"):

  * `_normalize` is *tolerant* -- it runs over whatever is already stored
    (or missing entirely) and always produces a legal, complete, ordered
    widget list, because stored data can predate a registry change (a
    widget key retired or added after the row was written) or, in
    principle, be malformed. It never raises.
  * `validate_update_entries` is *strict* -- it runs over a CEO-submitted
    PUT body and rejects (raises) on anything not already well-formed,
    because a client request is not "legacy data to tolerate", it's a
    fresh instruction the server should hold to the documented contract.

Preferences are presentation-only configuration (§4.6): this module never
touches `TaskORM`/`SpecificationORM`/`AgentORM` business state, never
recomputes `next_action` precedence, and is never consulted by
`workspace_overview`. Lifecycle events are logged (not published to the
EventBus/Timeline) -- a personal widget-layout change has no organizational
consequence for the rest of the company to observe, unlike an Employee
profile reassignment (Phase 1 decision, see docs/DECISIONS.md).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ...core.db_models import WorkspacePreferenceORM
from ...core.errors import StaleRevisionError
from .registry import REQUIRED_WIDGET_KEYS, SCHEMA_VERSION, WIDGETS, WIDGETS_BY_KEY
from .schemas import WidgetPreferenceEntry, WorkspacePreferences

logger = logging.getLogger(__name__)


class DuplicateWidgetError(ValueError):
    """A PUT body named the same widget_key more than once."""


class UnknownWidgetError(ValueError):
    """A PUT body named a widget_key outside the canonical registry."""


class MissingWidgetError(ValueError):
    """A PUT body omitted one or more registry widget_keys. The update
    contract requires the full catalog (exactly the registry's keys, each
    once) so "omitted" never has to be interpreted as "hide this" versus
    "forgot this" (§"Server-side validation" -- uniqueness/required)."""


class RequiredWidgetHiddenError(ValueError):
    """A PUT body set `visible=False` on a `required=True` widget."""


def _default_entry(widget_key: str) -> dict:
    definition = WIDGETS_BY_KEY[widget_key]
    return {
        "widget_key": definition.key,
        "visible": definition.default_visible,
        "order": definition.default_order,
        "span": definition.default_span,
    }


def _default_widgets() -> list[dict]:
    return [_default_entry(w.key) for w in sorted(WIDGETS, key=lambda w: w.default_order)]


def _resequence(entries: list[dict]) -> list[dict]:
    """Re-number `order` to a dense 0..N-1 sequence, preserving relative
    order (stable sort on the submitted/stored order, tie-broken by the
    registry's own default order so ties are deterministic)."""
    ordered = sorted(
        entries,
        key=lambda e: (e.get("order", WIDGETS_BY_KEY[e["widget_key"]].default_order), WIDGETS_BY_KEY[e["widget_key"]].default_order),
    )
    return [{**entry, "order": index} for index, entry in enumerate(ordered)]


def _normalize(raw: list[dict] | None) -> tuple[list[dict], bool, list[str]]:
    """Returns (normalized_widgets, changed, reasons). Never raises."""
    reasons: list[str] = []
    seen: set[str] = set()
    kept: list[dict] = []

    for entry in raw or []:
        key = entry.get("widget_key")
        if key not in WIDGETS_BY_KEY:
            reasons.append(f"dropped_unknown_widget:{key}")
            continue
        if key in seen:
            reasons.append(f"dropped_duplicate_widget:{key}")
            continue
        span = entry.get("span")
        if span not in ("full", "half"):
            span = WIDGETS_BY_KEY[key].default_span
            reasons.append(f"reset_invalid_span:{key}")
        visible = bool(entry.get("visible", WIDGETS_BY_KEY[key].default_visible))
        if key in REQUIRED_WIDGET_KEYS and not visible:
            visible = True
            reasons.append(f"restored_required_visible:{key}")
        order = entry.get("order")
        if not isinstance(order, int):
            order = WIDGETS_BY_KEY[key].default_order
            reasons.append(f"reset_invalid_order:{key}")
        seen.add(key)
        kept.append({"widget_key": key, "visible": visible, "order": order, "span": span})

    missing = [w.key for w in WIDGETS if w.key not in seen]
    for key in missing:
        kept.append(_default_entry(key))
        reasons.append(f"added_missing_widget:{key}")

    resequenced = _resequence(kept)
    changed = bool(reasons) or raw is None or len(raw) != len(resequenced)
    return resequenced, changed, reasons


def validate_update_entries(entries: list[WidgetPreferenceEntry]) -> list[dict]:
    keys = [e.widget_key for e in entries]
    if len(keys) != len(set(keys)):
        raise DuplicateWidgetError("Duplicate widget_key in update payload")

    unknown = set(keys) - set(WIDGETS_BY_KEY.keys())
    if unknown:
        raise UnknownWidgetError(f"Unknown widget_key(s): {sorted(unknown)}")

    missing = set(WIDGETS_BY_KEY.keys()) - set(keys)
    if missing:
        raise MissingWidgetError(f"Missing widget_key(s): {sorted(missing)}")

    for entry in entries:
        if entry.widget_key in REQUIRED_WIDGET_KEYS and not entry.visible:
            raise RequiredWidgetHiddenError(f"Widget {entry.widget_key!r} is required and cannot be hidden")

    dicts = [{"widget_key": e.widget_key, "visible": e.visible, "order": e.order, "span": e.span} for e in entries]
    return _resequence(dicts)


def _to_response(row: WorkspacePreferenceORM) -> WorkspacePreferences:
    return WorkspacePreferences(
        schema_version=row.schema_version,
        revision=row.revision,
        widgets=[WidgetPreferenceEntry.model_validate(w) for w in row.widgets],
        updated_at=row.updated_at,
    )


async def get_effective_preferences(session_factory, user_id: str, project_id: str) -> WorkspacePreferences:
    async with session_factory() as session:
        row = (
            await session.execute(
                select(WorkspacePreferenceORM).where(
                    WorkspacePreferenceORM.user_id == user_id, WorkspacePreferenceORM.project_id == project_id
                )
            )
        ).scalars().first()

        if row is None:
            normalized, _, reasons = _normalize(None)
            row = WorkspacePreferenceORM(
                user_id=user_id,
                project_id=project_id,
                schema_version=SCHEMA_VERSION,
                revision=1,
                widgets=normalized,
            )
            session.add(row)
            try:
                await session.commit()
                logger.info(
                    "workspace_preferences.initialized",
                    extra={"project_id": project_id, "revision": row.revision},
                )
            except IntegrityError:
                # Concurrent first-creation for the same (user, project): the
                # loser rolls back and reads the winner's row instead of
                # erroring (§1.14 concurrent-first-creation requirement).
                await session.rollback()
                row = (
                    await session.execute(
                        select(WorkspacePreferenceORM).where(
                            WorkspacePreferenceORM.user_id == user_id,
                            WorkspacePreferenceORM.project_id == project_id,
                        )
                    )
                ).scalars().first()
            await session.refresh(row)
            return _to_response(row)

        normalized, changed, reasons = _normalize(row.widgets)
        if changed:
            row.widgets = normalized
            row.revision += 1
            row.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(row)
            logger.info(
                "workspace_preferences.normalized",
                extra={"project_id": project_id, "revision": row.revision, "reasons": reasons},
            )
        return _to_response(row)


async def update_preferences(
    session_factory, user_id: str, project_id: str, expected_revision: int, entries: list[WidgetPreferenceEntry]
) -> WorkspacePreferences:
    normalized = validate_update_entries(entries)

    async with session_factory() as session:
        row = (
            await session.execute(
                select(WorkspacePreferenceORM).where(
                    WorkspacePreferenceORM.user_id == user_id, WorkspacePreferenceORM.project_id == project_id
                )
            )
        ).scalars().first()

        if row is None:
            # No prior GET ever happened for this (user, project) -- treat
            # "no row yet" as revision 0 so a first-ever PUT with
            # expected_revision=0 can still succeed.
            if expected_revision != 0:
                logger.info(
                    "workspace_preferences.stale_write_conflict",
                    extra={"project_id": project_id, "expected_revision": expected_revision, "current_revision": 0},
                )
                raise StaleRevisionError(current_revision=0)
            row = WorkspacePreferenceORM(
                user_id=user_id, project_id=project_id, schema_version=SCHEMA_VERSION, revision=1, widgets=normalized
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            logger.info(
                "workspace_preferences.updated",
                extra={"project_id": project_id, "revision": row.revision, "changed_widgets": [e.widget_key for e in entries]},
            )
            return _to_response(row)

        if row.revision != expected_revision:
            logger.info(
                "workspace_preferences.stale_write_conflict",
                extra={
                    "project_id": project_id,
                    "expected_revision": expected_revision,
                    "current_revision": row.revision,
                },
            )
            raise StaleRevisionError(current_revision=row.revision)

        row.widgets = normalized
        row.revision += 1
        row.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(row)
        logger.info(
            "workspace_preferences.updated",
            extra={"project_id": project_id, "revision": row.revision, "changed_widgets": [e.widget_key for e in entries]},
        )
        return _to_response(row)


async def reset_preferences(session_factory, user_id: str, project_id: str) -> WorkspacePreferences:
    defaults = _default_widgets()
    async with session_factory() as session:
        row = (
            await session.execute(
                select(WorkspacePreferenceORM).where(
                    WorkspacePreferenceORM.user_id == user_id, WorkspacePreferenceORM.project_id == project_id
                )
            )
        ).scalars().first()

        if row is None:
            row = WorkspacePreferenceORM(
                user_id=user_id, project_id=project_id, schema_version=SCHEMA_VERSION, revision=1, widgets=defaults
            )
            session.add(row)
        else:
            row.widgets = defaults
            row.revision += 1
            row.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(row)
        logger.info("workspace_preferences.reset", extra={"project_id": project_id, "revision": row.revision})
        return _to_response(row)
