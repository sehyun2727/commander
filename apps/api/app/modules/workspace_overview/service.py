"""Sprint 13 §6: the CEO Workspace projection service.

Read-only. Loads authoritative domain state through a small, fixed number
of bounded, sequential `select()` queries inside one session (same shape
as `situation/service.py`/`reports/service.py` -- see docs/DECISIONS.md
#219), assembles safe public schemas, and delegates next-action selection
to `next_action.derive()`.

This module never mutates a record, runs an agent, invokes a provider,
advances a workflow, approves a decision, or starts a mission -- it is not
a second WorkflowEngine.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from ...core.db_models import (
    AgentORM,
    ApprovalORM,
    EventORM,
    ProjectORM,
    RoleSingletonLockORM,
    SpecificationORM,
    TaskORM,
)
from ...core.lifecycle.agent_states import AgentState
from ...core.lifecycle.specification_states import SpecificationStatus, TERMINAL_SPECIFICATION_STATUSES
from ...core.lifecycle.task_states import TaskState
from ...templates import TEMPLATE
from . import next_action as next_action_policy
from .next_action import ApprovalFacts, LeadershipFacts, SpecFacts, TaskFacts, WorkspaceFacts
from .schemas import (
    MAX_ACTIVE_MISSIONS,
    MAX_EMPLOYEES,
    MAX_RECENT_ACTIVITY,
    MAX_RECENT_MISSIONS,
    SCHEMA_VERSION,
    ActivityItem,
    EmployeeCounts,
    EmployeeSummary,
    LeadershipSlot,
    MissionSummary,
    MissionSummaryItem,
    OrganizationSummary,
    PendingActions,
    PendingApprovalItem,
    PendingClarification,
    PendingFailure,
    PendingSpecificationReview,
    PlanningSummary,
    ProjectSummary,
    WorkspaceSnapshot,
)

_ACTIVE_TASK_STATES = {
    TaskState.ASSIGNED.value,
    TaskState.IN_PROGRESS.value,
    TaskState.IN_REVIEW.value,
    TaskState.PENDING_APPROVAL.value,
    TaskState.RETRYING.value,
}
_ATTENTION_TASK_STATES = {TaskState.FAILED.value, TaskState.BLOCKED.value}
_BUSY_AGENT_STATES = {
    AgentState.ASSIGNED.value,
    AgentState.PLANNING.value,
    AgentState.WORKING.value,
    AgentState.WAITING_REVIEW.value,
}
_ERROR_AGENT_STATES = {AgentState.BLOCKED.value, AgentState.FAILED.value}


def _mission_item(task: TaskORM) -> MissionSummaryItem:
    return MissionSummaryItem(
        id=task.id,
        title=task.title,
        state=task.state,
        priority=task.priority,
        specification_id=task.specification_id,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


async def get_workspace_snapshot(session_factory, project_id: str) -> WorkspaceSnapshot | None:
    async with session_factory() as session:
        project = await session.get(ProjectORM, project_id)
        if project is None:
            return None

        agents = list(
            (await session.execute(select(AgentORM).where(AgentORM.project_id == project_id))).scalars().all()
        )
        occupied_role_keys = set(
            (
                await session.execute(
                    select(RoleSingletonLockORM.role_key).where(RoleSingletonLockORM.project_id == project_id)
                )
            )
            .scalars()
            .all()
        )
        agents_by_role: dict[str, AgentORM] = {}
        for agent in agents:
            agents_by_role.setdefault(agent.role_key, agent)

        latest_spec = (
            await session.execute(
                select(SpecificationORM)
                .where(SpecificationORM.project_id == project_id)
                .order_by(SpecificationORM.created_at.desc())
                .limit(1)
            )
        ).scalars().first()

        has_execution_task = False
        if latest_spec is not None and latest_spec.status == SpecificationStatus.APPROVED.value:
            existing = (
                await session.execute(
                    select(TaskORM.id).where(TaskORM.specification_id == latest_spec.id).limit(1)
                )
            ).scalars().first()
            has_execution_task = existing is not None

        pending_approval = (
            await session.execute(
                select(ApprovalORM)
                .where(ApprovalORM.project_id == project_id, ApprovalORM.status == "pending")
                .order_by(ApprovalORM.created_at.asc())
                .limit(1)
            )
        ).scalars().first()

        has_any_task = (
            await session.execute(select(TaskORM.id).where(TaskORM.project_id == project_id).limit(1))
        ).scalars().first() is not None

        active_tasks = list(
            (
                await session.execute(
                    select(TaskORM)
                    .where(TaskORM.project_id == project_id, TaskORM.state.in_(_ACTIVE_TASK_STATES))
                    .order_by(TaskORM.updated_at.desc())
                    .limit(MAX_ACTIVE_MISSIONS)
                )
            )
            .scalars()
            .all()
        )
        attention_tasks = list(
            (
                await session.execute(
                    select(TaskORM)
                    .where(TaskORM.project_id == project_id, TaskORM.state.in_(_ATTENTION_TASK_STATES))
                    .order_by(TaskORM.updated_at.desc())
                    .limit(MAX_ACTIVE_MISSIONS)
                )
            )
            .scalars()
            .all()
        )
        recent_tasks = list(
            (
                await session.execute(
                    select(TaskORM)
                    .where(TaskORM.project_id == project_id)
                    .order_by(TaskORM.updated_at.desc())
                    .limit(MAX_RECENT_MISSIONS)
                )
            )
            .scalars()
            .all()
        )

        recent_events = list(
            (
                await session.execute(
                    select(EventORM)
                    .where(EventORM.project_id == project_id)
                    .order_by(EventORM.seq.desc())
                    .limit(MAX_RECENT_ACTIVITY)
                )
            )
            .scalars()
            .all()
        )
        max_seq = (
            await session.execute(select(func.max(EventORM.seq)).where(EventORM.project_id == project_id))
        ).scalar() or 0

    # ---- assemble facts for the pure next-action policy ----
    leadership_facts = tuple(
        LeadershipFacts(role_key=role.key, title=role.title, occupied=role.key in occupied_role_keys)
        for role in TEMPLATE.roles
        if role.category == "leadership"
    )
    spec_facts = (
        SpecFacts(
            id=latest_spec.id,
            status=latest_spec.status,
            current_version=latest_spec.current_version,
            turn_count=latest_spec.turn_count,
            clarification_questions=tuple(latest_spec.clarification_questions or []),
            has_execution_task=has_execution_task,
        )
        if latest_spec is not None
        else None
    )
    approval_facts = (
        ApprovalFacts(id=pending_approval.id, task_id=pending_approval.task_id, subject=pending_approval.subject)
        if pending_approval is not None
        else None
    )
    facts = WorkspaceFacts(
        project_id=project_id,
        latest_specification=spec_facts,
        pending_approval=approval_facts,
        failed_or_blocked_tasks=tuple(TaskFacts(id=t.id, title=t.title, state=t.state) for t in attention_tasks),
        active_tasks=tuple(TaskFacts(id=t.id, title=t.title, state=t.state) for t in active_tasks),
        leadership=leadership_facts,
        has_any_task=has_any_task,
    )
    action, focus = next_action_policy.derive(facts)

    # ---- pending_actions ----
    pending_actions = PendingActions(
        clarification=(
            PendingClarification(specification_id=latest_spec.id, questions=list(latest_spec.clarification_questions or []))
            if latest_spec is not None and latest_spec.status == SpecificationStatus.CLARIFICATION_REQUIRED.value
            else None
        ),
        specification_review=(
            PendingSpecificationReview(specification_id=latest_spec.id, version=latest_spec.current_version)
            if latest_spec is not None and latest_spec.status == SpecificationStatus.READY_FOR_REVIEW.value
            else None
        ),
        approval=(
            PendingApprovalItem(
                approval_id=pending_approval.id, task_id=pending_approval.task_id, subject=pending_approval.subject
            )
            if pending_approval is not None
            else None
        ),
        failure=(
            PendingFailure(resource_type="specification", resource_id=latest_spec.id, reason=latest_spec.stop_reason)
            if latest_spec is not None and latest_spec.status == SpecificationStatus.FAILED.value
            else (
                PendingFailure(resource_type="task", resource_id=attention_tasks[0].id, reason=None)
                if attention_tasks
                else None
            )
        ),
    )

    # ---- organization ----
    leadership_slots = [
        LeadershipSlot(
            role_key=role.key,
            title=role.title,
            occupied=role.key in occupied_role_keys,
            employee_id=agents_by_role.get(role.key).id if role.key in agents_by_role else None,
            employee_name=agents_by_role.get(role.key).name if role.key in agents_by_role else None,
        )
        for role in TEMPLATE.roles
        if role.category == "leadership"
    ]
    busy = sum(1 for a in agents if a.state in _BUSY_AGENT_STATES)
    error = sum(1 for a in agents if a.state in _ERROR_AGENT_STATES)
    idle = len(agents) - busy - error
    organization = OrganizationSummary(
        leadership=leadership_slots,
        counts=EmployeeCounts(total=len(agents), busy=busy, idle=idle, error=error),
        employees=[
            EmployeeSummary(id=a.id, name=a.name, role_key=a.role_key, state=a.state, current_task_id=a.current_task_id)
            for a in agents[:MAX_EMPLOYEES]
        ],
    )

    # ---- planning ----
    planning = PlanningSummary(
        active=latest_spec is not None
        and SpecificationStatus(latest_spec.status) not in TERMINAL_SPECIFICATION_STATUSES,
        specification_id=latest_spec.id if latest_spec is not None else None,
        status=latest_spec.status if latest_spec is not None else None,
        current_version=latest_spec.current_version if latest_spec is not None else None,
        turn_count=latest_spec.turn_count if latest_spec is not None else None,
        unresolved_questions=(
            len(latest_spec.clarification_questions or [])
            if latest_spec is not None and latest_spec.status == SpecificationStatus.CLARIFICATION_REQUIRED.value
            else 0
        ),
    )

    # ---- missions ----
    missions = MissionSummary(
        active=[_mission_item(t) for t in active_tasks],
        recent=[_mission_item(t) for t in recent_tasks],
    )

    # ---- recent activity (safe fields only, never raw payload) ----
    recent_activity = [
        ActivityItem(
            id=e.id,
            seq=e.seq,
            type=e.type,
            kind=e.kind,
            actor_role=e.actor_role,
            actor_name=e.actor_name,
            reason=e.reason,
            created_at=e.created_at,
        )
        for e in recent_events
    ]

    return WorkspaceSnapshot(
        schema_version=SCHEMA_VERSION,
        generated_at=datetime.now(timezone.utc),
        project=ProjectSummary(
            id=project.id, name=project.name, provider=project.provider, archived=project.archived, created_at=project.created_at
        ),
        organization=organization,
        focus=focus,
        pending_actions=pending_actions,
        next_action=action,
        planning=planning,
        missions=missions,
        recent_activity=recent_activity,
        event_cursor=int(max_seq),
    )
