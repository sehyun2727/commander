from __future__ import annotations

from ...core.contracts import AgentProfile
from ...core.db_models import AgentORM
from ...core.events import Actor, EventType, build_event
from ...core.interfaces.event_bus import EventBus

CEO_ACTOR = Actor(role="ceo", id="ceo", name="CEO")


async def get_profile(session_factory, agent_id: str) -> AgentProfile:
    async with session_factory() as session:
        agent = await session.get(AgentORM, agent_id)
        if agent is None:
            raise ValueError(f"Agent {agent_id} not found")
        return AgentProfile.model_validate(agent.profile)


async def update_profile(
    session_factory,
    event_bus: EventBus,
    agent_id: str,
    updates: dict,
) -> AgentProfile:
    """Merge `updates` (already `exclude_unset` from the request schema) onto
    the current profile and revalidate as a whole `AgentProfile`, so a
    partial PUT can never leave the stored profile in a state the model
    itself wouldn't accept."""
    async with session_factory() as session:
        agent = await session.get(AgentORM, agent_id)
        if agent is None:
            raise ValueError(f"Agent {agent_id} not found")
        current = AgentProfile.model_validate(agent.profile)
        changed_fields = [field for field, value in updates.items() if getattr(current, field) != value]
        merged = AgentProfile(**{**current.model_dump(), **updates})
        agent.profile = merged.model_dump(mode="json")
        project_id, agent_name = agent.project_id, agent.name
        await session.commit()

    if changed_fields:
        await event_bus.publish(
            build_event(
                type=EventType.AGENT_PROFILE_UPDATED,
                project_id=project_id,
                actor=CEO_ACTOR,
                payload={"agent_id": agent_id, "changed_fields": changed_fields},
                reason=f"CEO updated {agent_name}'s profile",
            )
        )
    return merged
