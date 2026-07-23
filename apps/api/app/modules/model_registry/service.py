from __future__ import annotations

from ...core.db_models import ProjectORM
from ...core.events import Actor, EventType, build_event
from ...core.interfaces.event_bus import EventBus
from .overrides import get_override, set_override
from .registry import ROLES, options_for_role, resolve

CEO_ACTOR = Actor(role="ceo", id="ceo", name="CEO")

# The reason string shown in the Timeline speaks in Employee terms (the
# brief's own example: "CEO reassigned Engineer to claude-sonnet-4-6"),
# even though the API/registry vocabulary is planner/builder/reviewer.
_ROLE_LABEL = {"planner": "PM", "builder": "Engineer", "reviewer": "Reviewer"}


async def provider_for(session_factory, project_id: str) -> str | None:
    async with session_factory() as session:
        project = await session.get(ProjectORM, project_id)
        return project.provider if project else None


async def effective_model(session_factory, provider: str, project_id: str, role: str) -> str:
    override = await get_override(session_factory, project_id, role)
    return override or resolve(provider, f"{role}-default")


async def list_catalog(session_factory, provider: str, project_id: str) -> list[dict]:
    catalog = []
    for role in ROLES:
        recommended = resolve(provider, f"{role}-default")
        override = await get_override(session_factory, project_id, role)
        catalog.append(
            {
                "role": role,
                "current_model": override or recommended,
                "recommended_model": recommended,
                "options": options_for_role(provider, role),
            }
        )
    return catalog


async def set_role_model(
    session_factory, event_bus: EventBus, provider: str, project_id: str, role: str, model_id: str
) -> None:
    if role not in ROLES:
        raise ValueError(f"unknown role {role!r}")
    if model_id not in options_for_role(provider, role):
        raise ValueError(f"{model_id!r} is not an available model for role {role!r}")

    previous = await effective_model(session_factory, provider, project_id, role)
    await set_override(session_factory, project_id, role, model_id)

    if previous != model_id:
        await event_bus.publish(
            build_event(
                type=EventType.MODEL_CHANGED,
                project_id=project_id,
                actor=CEO_ACTOR,
                payload={"role": role, "previous_model": previous, "new_model": model_id},
                reason=f"CEO reassigned {_ROLE_LABEL[role]} to {model_id}",
            )
        )
