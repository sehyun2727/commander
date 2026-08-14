from __future__ import annotations

from ...core.contracts import AgentProfile
from ...core.db_models import AgentORM, ProjectORM
from ...core.events import Actor, EventType, build_event
from ...core.interfaces.event_bus import EventBus
from ...templates import TEMPLATE
from ..model_registry import options_for_role

CEO_ACTOR = Actor(role="ceo", id="ceo", name="CEO")


class InvalidModelRefError(ValueError):
    """Raised when a profile PUT names a model_ref the registry doesn't
    know for this Employee's role -- a ValueError subclass so existing
    callers still catch it, but distinguishable so routes.py can answer
    422 instead of the generic 404 for an unknown agent."""


def _registry_role_for(agent_role: str) -> str:
    return TEMPLATE.roles_by_key[agent_role].model_ref.removesuffix("-default")


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
    itself wouldn't accept. A non-null model_ref must also name a model the
    registry recognizes for this Employee's role (Sprint 4.5 review note)."""
    async with session_factory() as session:
        agent = await session.get(AgentORM, agent_id)
        if agent is None:
            raise ValueError(f"Agent {agent_id} not found")
        current = AgentProfile.model_validate(agent.profile)
        changed_fields = [field for field, value in updates.items() if getattr(current, field) != value]
        merged = AgentProfile(**{**current.model_dump(), **updates})

        if merged.model_ref is not None:
            project = await session.get(ProjectORM, agent.project_id)
            registry_role = _registry_role_for(agent.role_key)
            if merged.model_ref not in options_for_role(project.provider, registry_role):
                raise InvalidModelRefError(
                    f"{merged.model_ref!r} is not a known model for role {agent.role_key!r} "
                    f"on provider {project.provider!r}"
                )

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
