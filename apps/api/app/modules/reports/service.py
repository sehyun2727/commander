from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from ...core.db_models import EventORM, ProjectORM, ReportORM
from ...core.events import EventType
from ...core.interfaces.event_bus import EventBus
from ...core.secrets import SecretsProvider
from ..costs import summary_since
from ..provider_gateway import build_gateway

REPORT_SYSTEM_PROMPT = (
    "You are writing a concise daily report for the CEO of an AI software "
    "company. Use plain, executive business language, never engineering "
    "jargon. Cover missions completed, any setbacks, decisions made, and "
    "spend for the period, then close with a one-line outlook."
)

_DECISION_TYPES = {EventType.APPROVAL_GRANTED, EventType.APPROVAL_REJECTED, EventType.APPROVAL_CHANGES_REQUESTED}
_MILESTONE_TYPES = _DECISION_TYPES | {EventType.TASK_COMPLETED, EventType.TASK_FAILED}


async def _events_since(session_factory, project_id: str, since: datetime) -> list[EventORM]:
    async with session_factory() as session:
        result = await session.execute(
            select(EventORM)
            .where(EventORM.project_id == project_id, EventORM.created_at >= since)
            .order_by(EventORM.seq.asc())
        )
        return list(result.scalars().all())


async def generate_report(
    session_factory,
    secrets: SecretsProvider,
    event_bus: EventBus,
    project_id: str,
) -> ReportORM | None:
    async with session_factory() as session:
        project = await session.get(ProjectORM, project_id)
    if project is None:
        return None

    period_end = datetime.now(timezone.utc)
    period_start = period_end - timedelta(hours=24)

    events = await _events_since(session_factory, project_id, period_start)
    missions_completed = sum(1 for e in events if e.type == EventType.TASK_COMPLETED.value)
    missions_failed = sum(1 for e in events if e.type == EventType.TASK_FAILED.value)
    decisions_made = sum(1 for e in events if e.type in {t.value for t in _DECISION_TYPES})
    highlights = [e.reason for e in events if e.type in {t.value for t in _MILESTONE_TYPES} and e.reason]
    payroll_usd = await summary_since(session_factory, project_id, period_start)

    facts_text = (
        f"Missions completed: {missions_completed}\n"
        f"Missions failed: {missions_failed}\n"
        f"Decisions made: {decisions_made}\n"
        f"Payroll this period: ${payroll_usd:.4f}\n"
        + ("Notable events:\n" + "\n".join(f"- {h}" for h in highlights[:10]) if highlights else "No notable events.")
    )

    gateway = build_gateway(
        project.provider,
        secrets,
        event_bus=event_bus,
        project_id=project_id,
        session_factory=session_factory,
    )
    result = await gateway.complete(
        "reporter-default",
        system=REPORT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": facts_text}],
        missions_completed=missions_completed,
        missions_failed=missions_failed,
        decisions_made=decisions_made,
        payroll_usd=payroll_usd,
        highlights=highlights,
        period_label="the last 24 hours",
    )

    report = ReportORM(
        project_id=project_id,
        period_start=period_start,
        period_end=period_end,
        summary_markdown=result.text,
    )
    async with session_factory() as session:
        session.add(report)
        await session.commit()
        await session.refresh(report)
    return report


async def list_reports(session_factory, project_id: str) -> list[ReportORM]:
    async with session_factory() as session:
        result = await session.execute(
            select(ReportORM).where(ReportORM.project_id == project_id).order_by(ReportORM.generated_at.desc())
        )
        return list(result.scalars().all())


async def get_report(session_factory, report_id: str) -> ReportORM | None:
    async with session_factory() as session:
        return await session.get(ReportORM, report_id)
