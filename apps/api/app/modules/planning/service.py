"""Sprint 12: thin planning entry points, same "plain async functions built
per call" convention as `tasks/service.py` -- no dedicated planning DI
singleton (PROGRESS.txt Phase 0 design decision 0.8 / docs/DECISIONS.md).
The API layer (Phase 3) calls these; they own nothing across calls.

`approve_specification`/`reject_specification`/`begin_execution` live here
rather than as `PlanningOrchestrator` methods (docs/DECISIONS.md #20x):
none of the three involves a PM/CTO turn or `AgentRuntime`/`ProviderGateway`
context, so folding them into the orchestrator would blur brief §5.1's
"Planning orchestration" vs "Specification repository/service" boundary
for no benefit -- they are CEO decisions on an already-drafted
Specification, not planning steps."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from ...core.db_models import ActiveSpecificationLockORM, SpecificationORM, SpecificationTurnORM, SpecificationVersionORM, TaskORM
from ...core.errors import SpecificationAlreadyExecutingError
from ...core.events import Actor, EventType, build_event
from ...core.interfaces.agent_runtime import AgentRuntime
from ...core.interfaces.event_bus import EventBus
from ...core.interfaces.workflow_engine import WorkflowEngine
from ...core.lifecycle.specification_states import SPECIFICATION_TRANSITIONS, SpecificationStatus
from ...core.lifecycle.state_machine import transition
from ...core.secrets import SecretsProvider
from ...templates import TEMPLATE
from ..tasks import assign_task, create_task
from .orchestrator import PlanningOrchestrator

CEO_ACTOR = Actor(role="ceo", id="ceo", name="CEO")


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def start_planning(
    session_factory,
    event_bus: EventBus,
    agent_runtime: AgentRuntime,
    secrets: SecretsProvider,
    project_id: str,
    request_text: str,
    source_task_id: str | None = None,
) -> SpecificationORM:
    orchestrator = PlanningOrchestrator(session_factory, event_bus, agent_runtime, secrets)
    return await orchestrator.start(project_id, request_text, source_task_id=source_task_id)


async def resume_after_clarification(
    session_factory,
    event_bus: EventBus,
    agent_runtime: AgentRuntime,
    secrets: SecretsProvider,
    specification_id: str,
    answers: list[str],
) -> SpecificationORM:
    orchestrator = PlanningOrchestrator(session_factory, event_bus, agent_runtime, secrets)
    return await orchestrator.resume_after_clarification(specification_id, answers)


async def submit_revision(
    session_factory,
    event_bus: EventBus,
    agent_runtime: AgentRuntime,
    secrets: SecretsProvider,
    specification_id: str,
    feedback: str,
) -> SpecificationORM:
    orchestrator = PlanningOrchestrator(session_factory, event_bus, agent_runtime, secrets)
    return await orchestrator.submit_revision(specification_id, feedback)


async def cancel_planning(
    session_factory,
    event_bus: EventBus,
    agent_runtime: AgentRuntime,
    secrets: SecretsProvider,
    specification_id: str,
    reason: str | None = None,
) -> bool:
    orchestrator = PlanningOrchestrator(session_factory, event_bus, agent_runtime, secrets)
    return await orchestrator.cancel(specification_id, reason)


async def get_specification(session_factory, specification_id: str) -> SpecificationORM | None:
    async with session_factory() as session:
        return await session.get(SpecificationORM, specification_id)


async def list_specifications(session_factory, project_id: str) -> list[SpecificationORM]:
    async with session_factory() as session:
        result = await session.execute(
            select(SpecificationORM)
            .where(SpecificationORM.project_id == project_id)
            .order_by(SpecificationORM.created_at.asc())
        )
        return list(result.scalars().all())


async def list_turns(session_factory, specification_id: str) -> list[SpecificationTurnORM]:
    async with session_factory() as session:
        result = await session.execute(
            select(SpecificationTurnORM)
            .where(SpecificationTurnORM.specification_id == specification_id)
            .order_by(SpecificationTurnORM.turn_index.asc())
        )
        return list(result.scalars().all())


async def list_versions(session_factory, specification_id: str) -> list[SpecificationVersionORM]:
    async with session_factory() as session:
        result = await session.execute(
            select(SpecificationVersionORM)
            .where(SpecificationVersionORM.specification_id == specification_id)
            .order_by(SpecificationVersionORM.version.asc())
        )
        return list(result.scalars().all())


async def current_version(session_factory, specification_id: str) -> SpecificationVersionORM | None:
    async with session_factory() as session:
        spec = await session.get(SpecificationORM, specification_id)
        if spec is None or spec.current_version == 0:
            return None
        result = await session.execute(
            select(SpecificationVersionORM).where(
                SpecificationVersionORM.specification_id == specification_id,
                SpecificationVersionORM.version == spec.current_version,
            )
        )
        return result.scalars().first()


async def _release_lock(session_factory, project_id: str) -> None:
    """Same shape as `PlanningOrchestrator._release_lock` -- duplicated
    rather than imported because that method is a private implementation
    detail of the turn-loop's own failure/cancel cleanup (Rule #1); this
    module only needs the same three lines for the CEO-decision paths
    that also end a Specification's non-terminal lifetime."""
    async with session_factory() as session:
        lock = await session.get(ActiveSpecificationLockORM, project_id)
        if lock is not None:
            await session.delete(lock)
            await session.commit()


async def approve_specification(session_factory, event_bus: EventBus, specification_id: str) -> SpecificationORM:
    async with session_factory() as session:
        spec = await session.get(SpecificationORM, specification_id)
        if spec is None:
            raise ValueError(f"no such specification {specification_id!r}")
        current = SpecificationStatus(spec.status)
        transition(current, SpecificationStatus.APPROVED, SPECIFICATION_TRANSITIONS)
        spec.status = SpecificationStatus.APPROVED.value
        spec.decided_at = _now()
        spec.updated_at = _now()
        await session.commit()
        project_id, version = spec.project_id, spec.current_version

    await _release_lock(session_factory, project_id)
    await event_bus.publish(
        build_event(
            type=EventType.SPECIFICATION_APPROVED,
            project_id=project_id,
            actor=CEO_ACTOR,
            payload={"specification_id": specification_id, "version": version},
            reason=f"CEO approved Project Specification v{version}",
        )
    )
    return await get_specification(session_factory, specification_id)


async def reject_specification(
    session_factory, event_bus: EventBus, specification_id: str, reason: str | None
) -> SpecificationORM:
    async with session_factory() as session:
        spec = await session.get(SpecificationORM, specification_id)
        if spec is None:
            raise ValueError(f"no such specification {specification_id!r}")
        current = SpecificationStatus(spec.status)
        transition(current, SpecificationStatus.REJECTED, SPECIFICATION_TRANSITIONS)
        spec.status = SpecificationStatus.REJECTED.value
        spec.decision_comment = reason
        spec.decided_at = _now()
        spec.updated_at = _now()
        await session.commit()
        project_id = spec.project_id

    await _release_lock(session_factory, project_id)
    await event_bus.publish(
        build_event(
            type=EventType.SPECIFICATION_REJECTED,
            project_id=project_id,
            actor=CEO_ACTOR,
            payload={"specification_id": specification_id},
            reason=reason or "CEO rejected the Project Specification",
        )
    )
    return await get_specification(session_factory, specification_id)


async def begin_execution(
    session_factory,
    event_bus: EventBus,
    agent_runtime: AgentRuntime,
    workflow_engine: WorkflowEngine,
    specification_id: str,
    priority: str = "normal",
) -> TaskORM:
    """Sprint 12 §4.7 approval gate, and the only path from an approved
    Specification into a Mission (docs/DECISIONS.md #197). Does nothing but
    validate approval + one-Mission-per-Specification, then delegate to the
    existing, unmodified `tasks.service.create_task`/`assign_task` -- the
    approval gate is enforced once, here, not threaded through
    WorkflowEngine (brief §5.1)."""
    async with session_factory() as session:
        spec = await session.get(SpecificationORM, specification_id)
        if spec is None:
            raise ValueError(f"no such specification {specification_id!r}")
        if SpecificationStatus(spec.status) != SpecificationStatus.APPROVED:
            raise ValueError(f"specification {specification_id!r} is not approved")
        project_id, version_number = spec.project_id, spec.current_version

        existing = await session.execute(
            select(TaskORM).where(TaskORM.specification_id == specification_id)
        )
        if existing.scalars().first() is not None:
            raise SpecificationAlreadyExecutingError(specification_id)

        version_result = await session.execute(
            select(SpecificationVersionORM).where(
                SpecificationVersionORM.specification_id == specification_id,
                SpecificationVersionORM.version == version_number,
            )
        )
        version = version_result.scalars().first()

    task = await create_task(
        session_factory,
        event_bus,
        project_id,
        version.title,
        version.problem_statement,
        priority,
        TEMPLATE.deliverable_type,
        specification_id=specification_id,
    )
    return await assign_task(session_factory, event_bus, agent_runtime, workflow_engine, task.id, None)
