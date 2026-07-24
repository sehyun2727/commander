"""Concrete AgentRuntime: owns Employee rows and their lifecycle transitions.

Every transition goes through core.lifecycle.state_machine.transition
against AGENT_TRANSITIONS, so an invalid move raises InvalidTransition
instead of silently corrupting state, and every successful move publishes
AgentStateChanged with the `reason` the caller gave.
"""

from __future__ import annotations

from ...core.contracts import AgentProfile
from ...core.db_models import AgentORM
from ...core.events import Actor, EventType, build_event
from ...core.interfaces.agent_runtime import AgentRuntime
from ...core.interfaces.event_bus import EventBus
from ...core.lifecycle.agent_states import AGENT_TRANSITIONS, AgentState
from ...core.lifecycle.state_machine import transition

SYSTEM_ACTOR = Actor(role="system", id="system", name="Commander")

DEPARTMENT_ROSTER = [
    dict(role="pm", name="Priya Shah", avatar_color="#8b5cf6"),
    dict(role="engineer", name="Devon Cole", avatar_color="#3b82f6"),
    dict(role="reviewer", name="Ari Kim", avatar_color="#14b8a6"),
]

# Every Employee is founded with the same neutral trait defaults (the
# AgentProfile field defaults themselves) — role-specific voice comes from
# PromptBuilder's immutable role contract layer (modules/prompt_builder),
# not from personality/working/decision style. Keyed by role so founding
# (create_department) and any future re-seed of a role can look its
# default up without re-deriving it.
DEFAULT_PROFILES: dict[str, AgentProfile] = {
    member["role"]: AgentProfile(name=member["name"], role=member["role"])
    for member in DEPARTMENT_ROSTER
}


class DBAgentRuntime(AgentRuntime):
    def __init__(self, session_factory, event_bus: EventBus) -> None:
        self._session_factory = session_factory
        self._event_bus = event_bus

    async def create_department(self, project_id: str) -> list[str]:
        agent_ids: list[str] = []
        async with self._session_factory() as session:
            rows = []
            for member in DEPARTMENT_ROSTER:
                row = AgentORM(
                    project_id=project_id,
                    role=member["role"],
                    name=member["name"],
                    profile=DEFAULT_PROFILES[member["role"]].model_dump(mode="json"),
                    avatar_color=member["avatar_color"],
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
                    payload={"agent_id": row.id, "role": row.role, "name": row.name},
                    reason=f"Company Department bootstrap hired a {row.role}",
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
