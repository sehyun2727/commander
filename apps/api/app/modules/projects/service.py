from __future__ import annotations

from sqlalchemy import select

from ...core.db_models import ProjectORM
from ...core.events import Actor, EventType, build_event
from ...core.interfaces.agent_runtime import AgentRuntime
from ...core.interfaces.event_bus import EventBus
from ...core.secrets import SecretsProvider

CEO_ACTOR = Actor(role="ceo", id="ceo", name="CEO")


async def create_project(
    session_factory,
    event_bus: EventBus,
    agent_runtime: AgentRuntime,
    name: str,
    provider: str,
) -> ProjectORM:
    async with session_factory() as session:
        project = ProjectORM(name=name, provider=provider)
        session.add(project)
        await session.commit()
        await session.refresh(project)

    await event_bus.publish(
        build_event(
            type=EventType.PROJECT_CREATED,
            project_id=project.id,
            actor=CEO_ACTOR,
            payload={"name": name},
            reason="CEO founded a new company",
        )
    )
    await agent_runtime.create_department(project.id)
    return project


async def list_projects(session_factory) -> list[ProjectORM]:
    async with session_factory() as session:
        result = await session.execute(select(ProjectORM).order_by(ProjectORM.created_at.asc()))
        return list(result.scalars().all())


async def get_project(session_factory, project_id: str) -> ProjectORM | None:
    async with session_factory() as session:
        return await session.get(ProjectORM, project_id)


async def archive_project(session_factory, event_bus: EventBus, project_id: str) -> ProjectORM | None:
    async with session_factory() as session:
        project = await session.get(ProjectORM, project_id)
        if project is None:
            return None
        project.archived = True
        await session.commit()
        await session.refresh(project)

    await event_bus.publish(
        build_event(
            type=EventType.PROJECT_ARCHIVED,
            project_id=project_id,
            actor=CEO_ACTOR,
            payload={},
            reason="CEO archived this company",
        )
    )
    return project


async def set_provider(session_factory, event_bus: EventBus, project_id: str, provider: str) -> ProjectORM | None:
    async with session_factory() as session:
        project = await session.get(ProjectORM, project_id)
        if project is None:
            return None
        previous = project.provider
        project.provider = provider
        await session.commit()
        await session.refresh(project)

    if previous != provider:
        await event_bus.publish(
            build_event(
                type=EventType.PROVIDER_CHANGED,
                project_id=project_id,
                actor=CEO_ACTOR,
                payload={"previous_provider": previous, "new_provider": provider},
                reason="CEO changed the AI provider in Company Settings",
            )
        )
    return project


async def update_settings(
    session_factory,
    event_bus: EventBus,
    secrets: SecretsProvider,
    project_id: str,
    name: str | None,
    provider: str | None,
    anthropic_api_key: str | None,
) -> ProjectORM | None:
    project = await get_project(session_factory, project_id)
    if project is None:
        return None

    if name and name != project.name:
        async with session_factory() as session:
            row = await session.get(ProjectORM, project_id)
            row.name = name
            await session.commit()

    if anthropic_api_key:
        await secrets.set("ANTHROPIC_API_KEY", anthropic_api_key)

    if provider and provider != project.provider:
        await set_provider(session_factory, event_bus, project_id, provider)

    return await get_project(session_factory, project_id)
