from __future__ import annotations

from sqlalchemy import select

from ...core.contracts import AgentProfile
from ...core.db_models import AgentORM, ProjectORM, TaskORM
from ...core.events import Actor, EventType, build_event
from ...core.events.base import Event
from ...core.interfaces.agent_runtime import AgentRuntime
from ...core.interfaces.event_bus import EventBus
from ...core.interfaces.workflow_engine import WorkflowEngine
from ...core.lifecycle.state_machine import transition
from ...core.lifecycle.task_states import TASK_TRANSITIONS, TaskState
from ...core.secrets import SecretsProvider
from ...templates import TEMPLATE
from .. import prompt_builder
from ..costs import record_usage
from ..provider_gateway import build_gateway

CEO_ACTOR = Actor(role="ceo", id="ceo", name="CEO")

_PM_KEY = TEMPLATE.roles[0].key


async def create_task(
    session_factory,
    event_bus: EventBus,
    project_id: str,
    title: str,
    description: str,
    priority: str,
) -> TaskORM:
    async with session_factory() as session:
        task = TaskORM(project_id=project_id, title=title, description=description, priority=priority)
        session.add(task)
        await session.commit()
        await session.refresh(task)

    await event_bus.publish(
        build_event(
            type=EventType.TASK_CREATED,
            project_id=project_id,
            actor=CEO_ACTOR,
            payload={"task_id": task.id, "title": title, "priority": priority},
            reason="CEO created a new mission",
        )
    )
    return task


async def list_tasks(session_factory, project_id: str) -> list[TaskORM]:
    async with session_factory() as session:
        result = await session.execute(
            select(TaskORM).where(TaskORM.project_id == project_id).order_by(TaskORM.created_at.asc())
        )
        return list(result.scalars().all())


async def get_task(session_factory, task_id: str) -> TaskORM | None:
    async with session_factory() as session:
        return await session.get(TaskORM, task_id)


async def assign_task(
    session_factory,
    event_bus: EventBus,
    agent_runtime: AgentRuntime,
    workflow_engine: WorkflowEngine,
    task_id: str,
    agent_id: str | None,
) -> TaskORM | None:
    async with session_factory() as session:
        task = await session.get(TaskORM, task_id)
        if task is None:
            return None

        if agent_id is None:
            result = await session.execute(
                select(AgentORM).where(AgentORM.project_id == task.project_id, AgentORM.role == _PM_KEY)
            )
            pm = result.scalars().first()
            agent_id = pm.id if pm else None

        current = TaskState(task.state)
        transition(current, TaskState.ASSIGNED, TASK_TRANSITIONS)
        task.state = TaskState.ASSIGNED.value
        await session.commit()
        await session.refresh(task)
        project_id, attempt = task.project_id, task.attempt

    if agent_id:
        await agent_runtime.set_current_task(agent_id, task_id)

    await event_bus.publish(
        build_event(
            type=EventType.TASK_ASSIGNED,
            project_id=project_id,
            actor=CEO_ACTOR,
            payload={"task_id": task_id, "agent_id": agent_id or "", "attempt": attempt},
            reason="CEO assigned this mission to the Department",
        )
    )
    await workflow_engine.start_task(task_id)
    return task


async def list_messages(event_bus: EventBus, project_id: str, task_id: str) -> list[Event]:
    return await event_bus.conversation_for(project_id, task_id=task_id)


async def post_message(
    session_factory,
    event_bus: EventBus,
    secrets: SecretsProvider,
    task_id: str,
    text: str,
) -> Event:
    """CEO sends a message in a Mission's Meeting; the Employee currently
    holding that Mission replies in persona (mock or real, per the
    company's active provider)."""
    async with session_factory() as session:
        task = await session.get(TaskORM, task_id)
        project_id = task.project_id
        project = await session.get(ProjectORM, project_id)

        result = await session.execute(
            select(AgentORM).where(AgentORM.project_id == project_id, AgentORM.current_task_id == task_id)
        )
        agent = result.scalars().first()
        if agent is None:
            result = await session.execute(
                select(AgentORM).where(AgentORM.project_id == project_id, AgentORM.role == _PM_KEY)
            )
            agent = result.scalars().first()

    await event_bus.publish(
        build_event(
            type=EventType.CONVERSATION_MESSAGE,
            project_id=project_id,
            actor=CEO_ACTOR,
            payload={"text": text, "task_id": task_id},
        )
    )

    gateway = build_gateway(
        project.provider,
        secrets,
        event_bus=event_bus,
        project_id=project_id,
        session_factory=session_factory,
    )
    model_ref = TEMPLATE.model_ref_for_role.get(agent.role, TEMPLATE.roles[0].model_ref)
    actor = Actor(role="employee", id=agent.id, name=agent.name)
    profile = AgentProfile.model_validate(agent.profile)
    buffer: list[str] = []
    usage: dict[str, int] = {}
    async for chunk in gateway.stream(
        model_ref,
        system=prompt_builder.build(profile, agent.role),
        messages=[{"role": "user", "content": text}],
        usage=usage,
        agent_override=profile.model_ref,
        task_title=task.title,
        task_description=task.description,
        context=f"The CEO just asked: {text}",
    ):
        buffer.append(chunk)
        await event_bus.publish_transient(
            build_event(
                type=EventType.CONVERSATION_MESSAGE_DELTA,
                project_id=project_id,
                actor=actor,
                payload={"text": chunk, "agent_id": agent.id, "task_id": task_id, "done": False},
            )
        )
    reply_text = "".join(buffer)
    await event_bus.publish_transient(
        build_event(
            type=EventType.CONVERSATION_MESSAGE_DELTA,
            project_id=project_id,
            actor=actor,
            payload={"text": "", "agent_id": agent.id, "task_id": task_id, "done": True},
        )
    )
    if usage:
        await record_usage(
            session_factory,
            project_id=project_id,
            task_id=task_id,
            agent_id=agent.id,
            role=agent.role,
            provider=gateway.provider_name,
            model=await gateway.resolve_model(model_ref, profile.model_ref),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )

    return await event_bus.publish(
        build_event(
            type=EventType.CONVERSATION_MESSAGE,
            project_id=project_id,
            actor=actor,
            payload={"text": reply_text, "agent_id": agent.id, "task_id": task_id},
        )
    )
