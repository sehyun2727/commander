"""Concrete AgentRuntime: owns Employee rows and their lifecycle transitions.

Every transition goes through core.lifecycle.state_machine.transition
against AGENT_TRANSITIONS, so an invalid move raises InvalidTransition
instead of silently corrupting state, and every successful move publishes
AgentStateChanged with the `reason` the caller gave.
"""

from __future__ import annotations

from sqlalchemy import select

from ...core.contracts import AgentProfile
from ...core.db_models import AgentORM
from ...core.errors import SingletonRoleViolation
from ...core.events import Actor, EventType, build_event
from ...core.interfaces.agent_runtime import AgentRuntime
from ...core.interfaces.event_bus import EventBus
from ...core.lifecycle.agent_states import AGENT_TRANSITIONS, AgentState
from ...core.lifecycle.state_machine import transition
from ...templates import TEMPLATE

SYSTEM_ACTOR = Actor(role="system", id="system", name="Commander")


async def create_employee(session_factory, project_id: str, role_key: str) -> AgentORM:
    """Add one Employee to `role_key`, enforcing Sprint 10 §10 singleton
    rule: a `singleton=True` Role (PM, Reviewer) may hold at most one
    Employee; a worker Role (Engineer) may hold any number.

    Not yet reachable from a route -- Sprint 11 wires an actual hiring
    endpoint through this function. It exists now so the enforcement rule
    and its race-condition analysis are settled before that UI lands (see
    docs/DECISIONS.md, Sprint 10 Phase 2).
    """
    role = TEMPLATE.roles_by_key[role_key]
    async with session_factory() as session:
        if role.singleton:
            existing = await session.execute(
                select(AgentORM).where(AgentORM.project_id == project_id, AgentORM.role_key == role_key)
            )
            if existing.scalars().first() is not None:
                raise SingletonRoleViolation(role_key)
        profile = AgentProfile(**role.default_profile)
        row = AgentORM(
            project_id=project_id,
            role_key=role_key,
            name=role.founding_name,
            profile=profile.model_dump(mode="json"),
            avatar_color=role.avatar_color,
            state=AgentState.IDLE.value,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


class DBAgentRuntime(AgentRuntime):
    def __init__(self, session_factory, event_bus: EventBus) -> None:
        self._session_factory = session_factory
        self._event_bus = event_bus

    async def create_department(self, project_id: str) -> list[str]:
        # The founding roster, role order, and default profiles all come
        # from the active company template's RoleSpecs -- founding never
        # hardcodes a role name the template doesn't already provide.
        # Sprint 11 §6.9: only RoleSpec.founding=True Roles are auto-seeded;
        # others (e.g. CTO) exist as vacant, hireable positions from day one.
        agent_ids: list[str] = []
        async with self._session_factory() as session:
            rows = []
            for role in TEMPLATE.roles:
                if not role.founding:
                    continue
                profile = AgentProfile(**role.default_profile)
                row = AgentORM(
                    project_id=project_id,
                    role_key=role.key,
                    name=role.founding_name,
                    profile=profile.model_dump(mode="json"),
                    avatar_color=role.avatar_color,
                    state=AgentState.IDLE.value,
                )
                session.add(row)
                rows.append(row)
            await session.commit()
            for row in rows:
                await session.refresh(row)
                agent_ids.append(row.id)

        for row in rows:
            await self._event_bus.publish(
                build_event(
                    type=EventType.AGENT_CREATED,
                    project_id=project_id,
                    actor=SYSTEM_ACTOR,
                    payload={"agent_id": row.id, "role": row.role_key, "name": row.name},
                    reason=f"Company Department bootstrap hired a {row.role_key}",
                )
            )

        # Each Employee introduces themself in the Timeline right after
        # founding (§6 onboarding) -- the template's own `intro` line,
        # posted as a task-less conversation event (task_id=None) so it
        # shows up in the company Timeline but never in a Mission Meeting.
        for row in rows:
            await self._event_bus.publish(
                build_event(
                    type=EventType.CONVERSATION_MESSAGE,
                    project_id=project_id,
                    actor=Actor(role="employee", id=row.id, name=row.name),
                    payload={"text": TEMPLATE.roles_by_key[row.role_key].intro, "agent_id": row.id, "task_id": None},
                    reason="Introduced themself at founding",
                )
            )
        return agent_ids

    async def transition(self, agent_id: str, target: AgentState, reason: str) -> None:
        async with self._session_factory() as session:
            row = await session.get(AgentORM, agent_id)
            if row is None:
                raise ValueError(f"unknown agent_id {agent_id}")
            current = AgentState(row.state)
            transition(current, target, AGENT_TRANSITIONS)
            row.state = target.value
            await session.commit()
            project_id = row.project_id
            agent_name = row.name

        await self._event_bus.publish(
            build_event(
                type=EventType.AGENT_STATE_CHANGED,
                project_id=project_id,
                actor=Actor(role="employee", id=agent_id, name=agent_name),
                payload={
                    "agent_id": agent_id,
                    "previous_state": current.value,
                    "new_state": target.value,
                },
                reason=reason,
            )
        )

    async def get_state(self, agent_id: str) -> AgentState:
        async with self._session_factory() as session:
            row = await session.get(AgentORM, agent_id)
            if row is None:
                raise ValueError(f"unknown agent_id {agent_id}")
            return AgentState(row.state)

    async def set_current_task(self, agent_id: str, task_id: str | None) -> None:
        async with self._session_factory() as session:
            row = await session.get(AgentORM, agent_id)
            if row is None:
                raise ValueError(f"unknown agent_id {agent_id}")
            row.current_task_id = task_id
            await session.commit()
