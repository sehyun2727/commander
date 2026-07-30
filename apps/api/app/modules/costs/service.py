from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from ...core.db_models import CostEntryORM
from ..model_registry import cost_for


def _month_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def record_usage(
    session_factory,
    *,
    project_id: str,
    task_id: str,
    agent_id: str,
    role: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> CostEntryORM:
    entry = CostEntryORM(
        project_id=project_id,
        task_id=task_id,
        agent_id=agent_id,
        role=role,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_for(model, input_tokens, output_tokens),
    )
    async with session_factory() as session:
        session.add(entry)
        await session.commit()
        await session.refresh(entry)
    return entry


async def summary_for_project(session_factory, project_id: str) -> tuple[float, list[tuple[str, float]]]:
    """This-month Payroll total plus a per-Employee breakdown, both scoped
    to the current calendar month — matches the "Payroll (this month)"
    vital on Headquarters."""
    since = _month_start()
    async with session_factory() as session:
        result = await session.execute(
            select(CostEntryORM.agent_id, func.sum(CostEntryORM.cost_usd))
            .where(CostEntryORM.project_id == project_id, CostEntryORM.created_at >= since)
            .group_by(CostEntryORM.agent_id)
        )
        rows = result.all()
    by_agent = [(agent_id, round(total or 0.0, 6)) for agent_id, total in rows]
    month_total = round(sum(total for _, total in by_agent), 6)
    return month_total, by_agent


async def summary_for_task(session_factory, task_id: str) -> float:
    """All-time spend for a single Mission — its "Mission Budget spent"."""
    async with session_factory() as session:
        result = await session.execute(
            select(func.sum(CostEntryORM.cost_usd)).where(CostEntryORM.task_id == task_id)
        )
        total = result.scalar()
    return round(total or 0.0, 6)


async def usage_for_task(session_factory, task_id: str) -> tuple[int, float]:
    """Cumulative (tokens, USD) spent on a Mission so far -- feeds the
    budget guard's per-stage check (Rule #13, Sprint 9)."""
    async with session_factory() as session:
        result = await session.execute(
            select(
                func.sum(CostEntryORM.input_tokens + CostEntryORM.output_tokens),
                func.sum(CostEntryORM.cost_usd),
            ).where(CostEntryORM.task_id == task_id)
        )
        tokens, usd = result.one()
    return int(tokens or 0), round(usd or 0.0, 6)


async def summary_since(session_factory, project_id: str, since: datetime) -> float:
    """Total spend for a Company from `since` to now — used by the Daily
    Report, which needs a fixed 24h window rather than Payroll's
    calendar-month scope."""
    async with session_factory() as session:
        result = await session.execute(
            select(func.sum(CostEntryORM.cost_usd)).where(
                CostEntryORM.project_id == project_id, CostEntryORM.created_at >= since
            )
        )
        total = result.scalar()
    return round(total or 0.0, 6)
