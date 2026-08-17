"""Sprint 12: thin planning entry points, same "plain async functions built
per call" convention as `tasks/service.py` -- no dedicated planning DI
singleton (PROGRESS.txt Phase 0 design decision 0.8 / docs/DECISIONS.md).
The API layer (Phase 3) calls these; they own nothing across calls."""

from __future__ import annotations

from sqlalchemy import select

from ...core.db_models import SpecificationORM, SpecificationTurnORM, SpecificationVersionORM
from ...core.interfaces.agent_runtime import AgentRuntime
from ...core.interfaces.event_bus import EventBus
from ...core.secrets import SecretsProvider
from .orchestrator import PlanningOrchestrator


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
