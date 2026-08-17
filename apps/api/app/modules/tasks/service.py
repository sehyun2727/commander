from __future__ import annotations

from sqlalchemy import select

from ...core.contracts import AgentProfile
from ...core.db_models import AgentORM, ProjectORM, TaskORM
from ...core.events import Actor, EventType, build_event
from ...core.events.base import Event
from ...core.interfaces.agent_runtime import AgentRuntime
from ...core.interfaces.event_bus import EventBus
from ...core.interfaces.workflow_engine import WorkflowEngine
from ...core.lifecycle.agent_states import AGENT_TRANSITIONS, AgentState
from ...core.lifecycle.state_machine import transition
from ...core.lifecycle.task_states import TASK_TRANSITIONS, TaskState
from ...core.secrets import SecretsProvider
from ...templates import TEMPLATE, first_stage_role_key
from .. import prompt_builder
from ..costs import record_usage
from ..provider_gateway import build_gateway

CEO_ACTOR = Actor(role="ceo", id="ceo", name="CEO")
SYSTEM_ACTOR = Actor(role="system", id="system", name="Commander")

# The CEO's one conversational counterpart (Rule #11) is whichever role
# does the pipeline's "plan" stage -- looked up by stage kind, not
# position, so this survives future roles being added (Sprint 9).
_PM_KEY = first_stage_role_key(TEMPLATE.pipeline, "plan")

_ORPHANABLE_STATES = (TaskState.IN_PROGRESS.value, TaskState.IN_REVIEW.value)

# An agent caught mid-pipeline by the same restart has no direct edge back
# to idle (see AGENT_TRANSITIONS) -- walk it there via FAILED, the state
# that best narrates "the work never finished." Each value is validated
# hop-by-hop through the real state machine before being applied.
_AGENT_RECOVERY_STEPS: dict[AgentState, tuple[AgentState, ...]] = {
    AgentState.ASSIGNED: (AgentState.FAILED, AgentState.IDLE),
    AgentState.PLANNING: (AgentState.FAILED, AgentState.IDLE),
    AgentState.WORKING: (AgentState.FAILED, AgentState.IDLE),
    AgentState.BLOCKED: (AgentState.FAILED, AgentState.IDLE),
    AgentState.WAITING_REVIEW: (AgentState.BLOCKED, AgentState.FAILED, AgentState.IDLE),
}


async def create_task(
    session_factory,
    event_bus: EventBus,
    project_id: str,
    title: str,
    description: str,
    priority: str,
    deliverable_type: str = TEMPLATE.deliverable_type,
    specification_id: str | None = None,
) -> TaskORM:
    async with session_factory() as session:
        task = TaskORM(
            project_id=project_id,
            title=title,
            description=description,
            priority=priority,
            deliverable_type=deliverable_type,
            specification_id=specification_id,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)

    await event_bus.publish(
        build_event(
            type=EventType.TASK_CREATED,
            project_id=project_id,
            actor=CEO_ACTOR,
            payload={"task_id": task.id, "title": title, "priority": priority},
            reason=(
                "CEO created a new mission"
                if specification_id is None
                else "Mission created from an approved Project Specification"
            ),
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


async def get_diff(session_factory, workspace_manager, task_id: str) -> tuple[str, bool] | None:
    task = await get_task(session_factory, task_id)
    if task is None or task.branch_name is None:
        return None
    return await workspace_manager.diff(task.project_id, task.branch_name)


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
                select(AgentORM).where(AgentORM.project_id == task.project_id, AgentORM.role_key == _PM_KEY)
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


async def recover_orphaned_tasks(session_factory, event_bus: EventBus) -> list[str]:
    """Startup sweep (Sprint 9): any Mission still `in_progress`/`in_review`
    when the process last stopped had its background pipeline coroutine
    die with it -- nothing will ever move it again, so this marks it
    `blocked` and tells the CEO via TaskRecovered rather than leaving it
    silently stuck forever. A clean shutdown never leaves a task in either
    state, so this is safe to run unconditionally on every boot.

    The Employee that was mid-pipeline on that same task is just as
    orphaned as the Mission -- its coroutine died too, so it's left
    parked in a busy AgentState (e.g. WORKING) that no future transition
    can legally start from. Left alone, the next Mission ever assigned to
    that Employee crashes with an InvalidTransition. This sweep resets
    any such Employee back to idle in the same pass."""
    async with session_factory() as session:
        result = await session.execute(select(TaskORM).where(TaskORM.state.in_(_ORPHANABLE_STATES)))
        rows = list(result.scalars().all())
        recovered: list[tuple[str, str, str]] = []
        recovered_task_ids: list[str] = []
        for row in rows:
            previous = TaskState(row.state)
            transition(previous, TaskState.BLOCKED, TASK_TRANSITIONS)
            row.state = TaskState.BLOCKED.value
            recovered.append((row.id, row.project_id, previous.value))
            recovered_task_ids.append(row.id)

        recovered_agents: list[tuple[str, str, str, str]] = []
        if recovered_task_ids:
            agent_result = await session.execute(
                select(AgentORM).where(AgentORM.current_task_id.in_(recovered_task_ids))
            )
            for agent_row in agent_result.scalars().all():
                agent_previous = AgentState(agent_row.state)
                steps = _AGENT_RECOVERY_STEPS.get(agent_previous)
                if steps is None:
                    continue
                current = agent_previous
                for step in steps:
                    transition(current, step, AGENT_TRANSITIONS)
                    current = step
                agent_row.state = AgentState.IDLE.value
                agent_row.current_task_id = None
                recovered_agents.append(
                    (agent_row.id, agent_row.project_id, agent_row.name, agent_previous.value)
                )

        await session.commit()

    for task_id, project_id, previous_state in recovered:
        await event_bus.publish(
            build_event(
                type=EventType.TASK_RECOVERED,
                project_id=project_id,
                actor=SYSTEM_ACTOR,
                payload={"task_id": task_id, "previous_state": previous_state},
                reason="Mission was mid-pipeline when Commander last restarted; no coroutine survived to finish it",
            )
        )
        await event_bus.publish(
            build_event(
                type=EventType.TASK_STATE_CHANGED,
                project_id=project_id,
                actor=SYSTEM_ACTOR,
                payload={
                    "task_id": task_id,
                    "previous_state": previous_state,
                    "new_state": TaskState.BLOCKED.value,
                },
                reason="Orphan recovery on restart",
            )
        )

    for agent_id, project_id, agent_name, previous_state in recovered_agents:
        await event_bus.publish(
            build_event(
                type=EventType.AGENT_STATE_CHANGED,
                project_id=project_id,
                actor=Actor(role="employee", id=agent_id, name=agent_name),
                payload={
                    "agent_id": agent_id,
                    "previous_state": previous_state,
                    "new_state": AgentState.IDLE.value,
                },
                reason="Orphan recovery on restart: this Employee's mission never finished, so they're back to idle and can take new work",
            )
        )
    return [task_id for task_id, _, _ in recovered]


async def cancel_task(
    workflow_engine: WorkflowEngine, task_id: str, reason: str
) -> bool:
    """CEO-initiated cancel (Sprint 9); delegates the state transition and
    any in-flight asyncio.Task cancellation to the engine, which is the
    only place that knows what's currently running."""
    return await workflow_engine.cancel_task(task_id, reason)


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
                select(AgentORM).where(AgentORM.project_id == project_id, AgentORM.role_key == _PM_KEY)
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
    model_ref = TEMPLATE.roles_by_key.get(agent.role_key, TEMPLATE.roles_by_key[_PM_KEY]).model_ref
    actor = Actor(role="employee", id=agent.id, name=agent.name)
    profile = AgentProfile.model_validate(agent.profile)
    buffer: list[str] = []
    usage: dict[str, int] = {}
    async for chunk in gateway.stream(
        model_ref,
        system=prompt_builder.build(profile, agent.role_key),
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
            role=agent.role_key,
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
