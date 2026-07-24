"""Situation Report: a glanceable PM-voiced one-liner for Headquarters —
NOT the Daily Report (see reports/). Deliberately ephemeral and uncached
(Sprint 4.7 judgment call, docs/DECISIONS.md "Sprint 4.7"): regenerated on
every request rather than persisted, since mock mode is free and a real
call here is the same order of cost as any other single pipeline turn.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from ...core.db_models import ApprovalORM, EventORM, ProjectORM, TaskORM
from ...core.interfaces.event_bus import EventBus
from ...core.lifecycle.task_states import TaskState
from ...core.secrets import SecretsProvider
from ..provider_gateway import build_gateway

SITUATION_SYSTEM_PROMPT = (
    "You are the PM of an AI software company, writing exactly one or two "
    "glanceable sentences for the CEO's Headquarters dashboard -- not a "
    "report, a single at-a-glance line on the current state: pending "
    "decisions, missions in flight, and the last notable thing that "
    "happened. Plain business language, no engineering jargon, no "
    "greeting, no signature, no markdown."
)

_IN_FLIGHT_STATES = {TaskState.ASSIGNED.value, TaskState.IN_PROGRESS.value, TaskState.IN_REVIEW.value}


async def _facts(session_factory, project_id: str) -> dict:
    async with session_factory() as session:
        pending_result = await session.execute(
            select(ApprovalORM).where(ApprovalORM.project_id == project_id, ApprovalORM.status == "pending")
        )
        pending_decisions = len(list(pending_result.scalars().all()))

        active_result = await session.execute(
            select(TaskORM).where(TaskORM.project_id == project_id, TaskORM.state.in_(_IN_FLIGHT_STATES))
        )
        missions_active = len(list(active_result.scalars().all()))

        last_event_result = await session.execute(
            select(EventORM)
            .where(EventORM.project_id == project_id, EventORM.reason.is_not(None))
            .order_by(EventORM.seq.desc())
            .limit(1)
        )
        last_event = last_event_result.scalars().first()

    return {
        "pending_decisions": pending_decisions,
        "missions_active": missions_active,
        "last_event_reason": last_event.reason if last_event else None,
    }


def _fallback_text(facts: dict) -> str:
    """Cheap deterministic sentence, used verbatim in mock mode and as the
    fallback if a real provider call fails -- the Situation Report must
    never be the thing that breaks a page load."""
    pending, active, last_reason = facts["pending_decisions"], facts["missions_active"], facts["last_event_reason"]
    pieces = []
    if pending:
        pieces.append(f"{pending} decision{'s' if pending != 1 else ''} waiting on you")
    if active:
        pieces.append(f"{active} mission{'s' if active != 1 else ''} in flight")
    base = (
        "Everything's quiet right now — no missions in flight and nothing needs your decision."
        if not pieces
        else "Right now: " + ", ".join(pieces) + "."
    )
    if last_reason:
        base += f" Most recently: {last_reason}."
    return base


async def get_situation(
    session_factory,
    secrets: SecretsProvider,
    event_bus: EventBus,
    project_id: str,
) -> tuple[str, datetime] | None:
    async with session_factory() as session:
        project = await session.get(ProjectORM, project_id)
    if project is None:
        return None

    facts = await _facts(session_factory, project_id)
    fallback = _fallback_text(facts)

    try:
        gateway = build_gateway(
            project.provider,
            secrets,
            event_bus=event_bus,
            project_id=project_id,
            session_factory=session_factory,
        )
        result = await gateway.complete(
            "situation-default",
            system=SITUATION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": fallback}],
            **facts,
        )
        text = result.text.strip() or fallback
    except Exception:  # noqa: BLE001 - a flaky provider must never break Headquarters
        text = fallback

    return text, datetime.now(timezone.utc)
