"""Concrete AgentRuntime: owns Employee rows and their lifecycle transitions.

Every transition goes through core.lifecycle.state_machine.transition
against AGENT_TRANSITIONS, so an invalid move raises InvalidTransition
instead of silently corrupting state, and every successful move publishes
AgentStateChanged with the `reason` the caller gave.
"""

from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError

from ...core.contracts import AgentProfile
from ...core.db_models import AgentORM, RoleSingletonLockORM
from ...core.errors import SingletonRoleViolation
from ...core.events import Actor, EventType, build_event
from ...core.interfaces.agent_runtime import AgentRuntime
from ...core.interfaces.event_bus import EventBus
from ...core.lifecycle.agent_states import AGENT_TRANSITIONS, AgentState
from ...core.lifecycle.state_machine import transition
from ..model_registry import options_for_role
from ..skill_templates import DEFAULT_SKILL_TEMPLATE_KEY, SKILL_TEMPLATES_BY_KEY
from ...templates import TEMPLATE
from ...templates.software_company import RoleSpec

SYSTEM_ACTOR = Actor(role="system", id="system", name="Commander")
CEO_ACTOR = Actor(role="ceo", id="ceo", name="CEO")

EMPLOYEE_NAME_MAX_LEN = 100


class InvalidRoleError(ValueError):
    """Raised when a hire names a role_key the active template doesn't define."""


class InvalidModelRefError(ValueError):
    """Raised when a hire names a model_ref the registry doesn't offer for
    this Employee's Role/provider."""


class InvalidSkillTemplateError(ValueError):
    """Raised when a hire names a skill_template_key outside the canonical
    skill_templates registry (Sprint 11 §4.6)."""


class InvalidEmployeeNameError(ValueError):
    """Raised when a hire's employee name is empty or too long."""


def _registry_role_for(role: RoleSpec) -> str:
    return role.model_ref.removesuffix("-default")


async def hire_employee(
    session_factory,
    event_bus: EventBus,
    project_id: str,
    provider: str,
    role_key: str,
    name: str,
    model_ref: str | None = None,
    skill_template_key: str | None = None,
) -> AgentORM:
    """The one authoritative hiring path (Sprint 11 §6.4). Validates Role,
    model, skill template, and name; enforces the Role's singleton policy
    atomically via `RoleSingletonLockORM`'s composite primary key rather
    than a service-layer check-then-insert (docs/DECISIONS.md #167, #18x);
    persists the Employee; and emits AGENT_HIRED only once the transaction
    has actually committed (Rule #3, §6.7 -- never a success event before
    persistence)."""
    role = TEMPLATE.roles_by_key.get(role_key)
    if role is None:
        raise InvalidRoleError(f"unknown role {role_key!r}")

    employee_name = name.strip()
    if not employee_name:
        raise InvalidEmployeeNameError("employee name must not be empty")
    if len(employee_name) > EMPLOYEE_NAME_MAX_LEN:
        raise InvalidEmployeeNameError(f"employee name must be at most {EMPLOYEE_NAME_MAX_LEN} characters")

    resolved_skill_key = skill_template_key or DEFAULT_SKILL_TEMPLATE_KEY
    if resolved_skill_key not in SKILL_TEMPLATES_BY_KEY:
        raise InvalidSkillTemplateError(f"unknown skill template {resolved_skill_key!r}")

    if model_ref is not None and model_ref not in options_for_role(provider, _registry_role_for(role)):
        raise InvalidModelRefError(
            f"{model_ref!r} is not a known model for role {role_key!r} on provider {provider!r}"
        )

    profile = AgentProfile(
        name=employee_name, role=role_key, model_ref=model_ref, skill_template_key=resolved_skill_key
    )
    agent_id = str(uuid.uuid4())

    async with session_factory() as session:
        if role.singleton:
            # Fast, non-authoritative pre-check: a clean, cheap error on
            # the overwhelmingly common non-racing path. The composite
            # primary key insert below -- not this check -- is what
            # actually makes concurrent hires race-safe.
            existing_lock = await session.get(RoleSingletonLockORM, (project_id, role_key))
            if existing_lock is not None:
                raise SingletonRoleViolation(role_key)

        row = AgentORM(
            id=agent_id,
            project_id=project_id,
            role_key=role_key,
            name=employee_name,
            profile=profile.model_dump(mode="json"),
            avatar_color=role.avatar_color,
            state=AgentState.IDLE.value,
        )
        session.add(row)
        if role.singleton:
            session.add(RoleSingletonLockORM(project_id=project_id, role_key=role_key, agent_id=agent_id))

        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise SingletonRoleViolation(role_key)
        await session.refresh(row)

    await event_bus.publish(
        build_event(
            type=EventType.AGENT_HIRED,
            project_id=project_id,
            actor=CEO_ACTOR,
            payload={
                "agent_id": agent_id,
                "role_key": role_key,
                "model_ref": model_ref,
                "skill_template_key": resolved_skill_key,
            },
            reason=f"CEO hired a new {role.title}",
        )
    )
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
                agent_id = str(uuid.uuid4())
                profile = AgentProfile(**role.default_profile)
                row = AgentORM(
                    id=agent_id,
                    project_id=project_id,
                    role_key=role.key,
                    name=role.founding_name,
                    profile=profile.model_dump(mode="json"),
                    avatar_color=role.avatar_color,
                    state=AgentState.IDLE.value,
                )
                session.add(row)
                rows.append(row)
                if role.singleton:
                    # Founding never races (each Role appears at most once
                    # in TEMPLATE.roles), but a founding PM/Reviewer still
                    # has to claim its singleton lock row now -- otherwise
                    # a later hire_employee() call for the same Role would
                    # find no lock and insert a second Employee straight
                    # past the atomic guard (Sprint 11 §4.10).
                    session.add(RoleSingletonLockORM(project_id=project_id, role_key=role.key, agent_id=agent_id))
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
