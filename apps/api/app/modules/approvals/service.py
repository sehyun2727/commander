"""Approvals module.

Owns the Approval row lifecycle. Learns which task needs an Approval only
via ApprovalRequested (published by workflow_engine) — this module never
reaches into workflow_engine's internals. Deciding an approval delegates
the resulting task-state transition to workflow_engine.resume_after_decision
rather than mutating task state here directly.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from ...core.db_models import ApprovalORM, ProjectORM
from ...core.interfaces.workflow_engine import WorkflowEngine


async def list_pending(session_factory, project_id: str | None, owner_id: str | None = None) -> list[ApprovalORM]:
    async with session_factory() as session:
        stmt = select(ApprovalORM).where(ApprovalORM.status == "pending")
        if project_id:
            stmt = stmt.where(ApprovalORM.project_id == project_id)
        else:
            # No project_id means "across every one of my companies" -- must
            # still be scoped to this account, never every account's (Rule #15).
            stmt = stmt.join(ProjectORM, ProjectORM.id == ApprovalORM.project_id).where(
                ProjectORM.owner_id == owner_id
            )
        stmt = stmt.order_by(ApprovalORM.created_at.asc())
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def list_all(session_factory, project_id: str) -> list[ApprovalORM]:
    async with session_factory() as session:
        result = await session.execute(
            select(ApprovalORM)
            .where(ApprovalORM.project_id == project_id)
            .order_by(ApprovalORM.created_at.desc())
        )
        return list(result.scalars().all())


async def decide(
    session_factory,
    workflow_engine: WorkflowEngine,
    approval_id: str,
    decision: str,
    comment: str | None,
) -> ApprovalORM | None:
    async with session_factory() as session:
        approval = await session.get(ApprovalORM, approval_id)
        if approval is None or approval.status != "pending":
            return None
        approval.decided_at = datetime.now(timezone.utc)
        await session.commit()
        task_id = approval.task_id

    await workflow_engine.resume_after_decision(task_id, decision, comment)

    async with session_factory() as session:
        return await session.get(ApprovalORM, approval_id)
