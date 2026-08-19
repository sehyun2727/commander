"""CommanderWorkflowEngine: PM -> Engineer -> Reviewer -> CEO Decision.

Runs as a background asyncio task per mission so the API stays responsive
(routes fire-and-forget via `start_task`/`resume_after_decision`). Each
step opens its own DB session rather than holding one across the
0.5-1.5s pacing sleeps, and every state transition + narrative beat is
published to the Event Bus so the Timeline/SSE feed feels alive.

Failure handling here is intentionally minimal for this sprint: a
provider error fails the task and frees the agent. The full retry-budget /
escalation policy in docs/backend/workflow/FAILURE_HANDLING.md is out of
scope — see docs/DECISIONS.md.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import random
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select

from ...core.contracts import AgentProfile
from ...core.db_models import AgentORM, ApprovalORM, TaskORM
from ...core.errors import (
    BudgetExceededError,
    EmployeeSurrenderedError,
    SelfCorrectionExhaustedError,
    WorkspaceConflictError,
)
from ...core.events import Actor, EventType, build_event
from ...core.interfaces.agent_runtime import AgentRuntime
from ...core.interfaces.event_bus import EventBus
from ...core.interfaces.provider_gateway import ProviderGateway
from ...core.interfaces.sandbox import SandboxRunner
from ...core.interfaces.workflow_engine import WorkflowEngine
from ...core.interfaces.workspace_manager import WorkspaceManager
from ...core.lifecycle.agent_states import AgentState
from ...core.lifecycle.state_machine import InvalidTransition, transition
from ...core.lifecycle.task_states import TASK_TRANSITIONS, TaskState
from ...core.logging import agent_id_var, project_id_var, task_id_var
from ...core.secrets import SecretsProvider
from ...core.config import settings
from ...templates import TEMPLATE, StageSpec, first_stage_index
from ...templates.software_company import RoleSpec
from .. import prompt_builder
from ..agent_harness.budget import HarnessBudget
from ..agent_harness.context import LoopState, ToolRunContext
from ..agent_harness.orchestrator import MAX_CORRECTION_ATTEMPTS, run_tool_loop
from ..agent_harness.output import bound_output
from ..agent_harness.permissions import resolve_permitted_tools
from ..costs import record_usage, usage_for_task
from ..model_registry import RECOMMENDED_PROVIDER
from ..provider_gateway import build_gateway
from ..sandbox import detect_checks, get_execution_enabled
from ..skill_templates.registry import GENERALIST, SKILL_TEMPLATES_BY_KEY
from . import parsing
from .employee_resolution import resolve_employee_for_role

logger = logging.getLogger("commander.workflow_engine")

SYSTEM_ACTOR = Actor(role="system", id="system", name="Commander")
CEO_ACTOR = Actor(role="ceo", id="ceo", name="CEO")

# The engine iterates `TEMPLATE.pipeline` (a tuple of `StageSpec`) rather
# than three named role variables (Sprint 9, Rule #16) -- see
# docs/DECISIONS.md "Sprint 4.7" for why the pipeline's per-`kind`
# *behavior* is still concrete engine logic, and the Sprint 9 entry for
# why its *sequence* moved to template data. `_REWORK_STAGE_INDEX` is
# where a CEO "request changes" decision resumes: the first "produce"
# stage, skipping any earlier planning rather than redoing it.
_REWORK_STAGE_INDEX = first_stage_index(TEMPLATE.pipeline, "produce")

# Sprint 19 §4.8 load-smoke finding: the founding roster seeds exactly one
# Employee per Role (Sprint 10 §12), so concurrent Missions in one Company
# routinely contend for the same Employee. `resolve_employee_for_role`'s
# own fallback rule can hand back a busy Employee when nobody's idle, and
# a race between two concurrent pipelines can also both resolve the same
# idle Employee before either claims it. `_claim_agent` bounds how long it
# waits for that Employee to actually go idle before giving up (Rule #13:
# budgeted, never forever).
_AGENT_CLAIM_TIMEOUT_SECONDS = 120.0
_AGENT_CLAIM_POLL_SECONDS = 0.2


@dataclass(frozen=True)
class TaskSnapshot:
    """Immutable point-in-time view of a `TaskORM`, threaded through the
    pipeline stages instead of the ORM row itself. Each stage opens its own
    session (see module docstring); holding the row across those sessions
    let a stage read fields another stage had already changed in the DB but
    not on this object -- `dataclasses.replace` after each mutating stage
    keeps the two in sync explicitly instead of by accident (Sprint 9)."""

    id: str
    project_id: str
    title: str
    description: str
    deliverable_type: str
    branch_name: str | None
    attempt: int
    created_at: datetime

    @classmethod
    def from_orm(cls, task: TaskORM) -> "TaskSnapshot":
        return cls(
            id=task.id,
            project_id=task.project_id,
            title=task.title,
            description=task.description,
            deliverable_type=task.deliverable_type,
            branch_name=task.branch_name,
            attempt=task.attempt,
            created_at=task.created_at,
        )


def _pause() -> "asyncio.Future[None]":
    if not settings.commander_pacing_enabled:
        return asyncio.sleep(0)
    return asyncio.sleep(random.uniform(0.5, 1.5))


def _agent_model_override(agent: AgentORM) -> str | None:
    """The Employee's own model override (three-tier resolution's top
    tier), read straight from the persisted profile JSON rather than
    round-tripping through a full `AgentProfile.model_validate` when only
    this one field is needed."""
    return agent.profile.get("model_ref")


class CommanderWorkflowEngine(WorkflowEngine):
    def __init__(
        self,
        session_factory,
        event_bus: EventBus,
        agent_runtime: AgentRuntime,
        secrets: SecretsProvider,
        workspace_manager: WorkspaceManager,
        sandbox_runner: SandboxRunner,
    ) -> None:
        self._session_factory = session_factory
        self._event_bus = event_bus
        self._agent_runtime = agent_runtime
        self._secrets = secrets
        self._workspace_manager = workspace_manager
        self._sandbox_runner = sandbox_runner
        # Execution registry (Sprint 9): the in-memory asyncio.Task backing
        # each running mission, so `cancel_task` has something concrete to
        # cancel and orphan recovery (main.py lifespan) knows this process
        # never has any of these running right after a restart. Reason
        # strings for a cancel-in-flight are handed off here because the
        # CancelledError that `.cancel()` raises inside `_run_pipeline`
        # carries no payload of its own.
        self._running: dict[str, asyncio.Task] = {}
        self._cancel_reasons: dict[str, str] = {}

    # --- public API -----------------------------------------------------

    async def start_task(self, task_id: str) -> None:
        self._spawn(task_id, resume_from=0)

    def _spawn(self, task_id: str, resume_from: int, ceo_comment: str | None = None) -> None:
        async def _runner() -> None:
            token = task_id_var.set(task_id)
            try:
                await self._run_pipeline(task_id, resume_from=resume_from, ceo_comment=ceo_comment)
            finally:
                task_id_var.reset(token)
                self._running.pop(task_id, None)

        self._running[task_id] = asyncio.create_task(_runner())

    async def cancel_task(self, task_id: str, reason: str) -> bool:
        """CEO-initiated cancel (Sprint 9). Returns False if the mission
        isn't in a cancellable state. A running pipeline is cancelled via
        its asyncio.Task -- `_run_pipeline`'s own CancelledError handler
        does the state transition + agent release, so the DB write happens
        exactly once no matter how many times this is called. If nothing
        is running in this process (mission already ended, or this is a
        second process after a restart with no in-memory task), fall back
        to finishing it directly."""
        async with self._session_factory() as session:
            task_row = await session.get(TaskORM, task_id)
            if task_row is None:
                return False
            current = TaskState(task_row.state)
            if TaskState.CANCELLED not in TASK_TRANSITIONS.get(current, set()):
                return False

        running = self._running.get(task_id)
        if running is not None and not running.done():
            self._cancel_reasons[task_id] = reason
            running.cancel()
            return True

        await self._finish_task(task_id, TaskState.CANCELLED, reason, EventType.TASK_CANCELLED)
        return True

    async def resume_after_decision(
        self, task_id: str, decision: str, comment: str | None
    ) -> None:
        if decision == "approve":
            await self._approve_task(task_id, comment)
        elif decision == "reject":
            await self._finish_task(task_id, TaskState.CANCELLED, comment, EventType.TASK_CANCELLED)
        else:  # request_changes
            async with self._session_factory() as session:
                task = await session.get(TaskORM, task_id)
                task.attempt += 1
                self._apply_task_transition(task, TaskState.IN_PROGRESS)
                result = await session.execute(
                    select(ApprovalORM)
                    .where(ApprovalORM.task_id == task_id, ApprovalORM.status == "pending")
                    .order_by(ApprovalORM.created_at.desc())
                )
                approval = result.scalars().first()
                if approval:
                    approval.status = "changes_requested"
                    approval.comment = comment
                approval_id = approval.id if approval else None
                await session.commit()
                project_id, attempt = task.project_id, task.attempt
            if approval_id:
                await self._event_bus.publish(
                    build_event(
                        type=EventType.APPROVAL_CHANGES_REQUESTED,
                        project_id=project_id,
                        actor=CEO_ACTOR,
                        payload={"approval_id": approval_id},
                        reason=comment,
                    )
                )
            await self._event_bus.publish(
                build_event(
                    type=EventType.TASK_RETRIED,
                    project_id=project_id,
                    actor=CEO_ACTOR,
                    payload={"task_id": task_id, "attempt": attempt},
                    reason=comment or "CEO requested changes",
                )
            )
            self._spawn(task_id, resume_from=_REWORK_STAGE_INDEX, ceo_comment=comment)

    # --- internals --------------------------------------------------------

    async def _gateway_for(self, project_id: str) -> ProviderGateway:
        async with self._session_factory() as session:
            from ...core.db_models import ProjectORM

            project = await session.get(ProjectORM, project_id)
            provider_name = project.provider if project else RECOMMENDED_PROVIDER
        return build_gateway(
            provider_name,
            self._secrets,
            event_bus=self._event_bus,
            project_id=project_id,
            session_factory=self._session_factory,
        )

    @staticmethod
    def _apply_task_transition(task: TaskORM, target: TaskState) -> TaskState:
        current = TaskState(task.state)
        transition(current, target, TASK_TRANSITIONS)
        task.state = target.value
        return current

    @staticmethod
    def _branch_name_for(task_id: str) -> str:
        return f"mission/{task_id[:8]}"

    async def _set_task_state(
        self, task_id: str, target: TaskState, reason: str, actor: Actor
    ) -> tuple[str, TaskState]:
        async with self._session_factory() as session:
            task = await session.get(TaskORM, task_id)
            previous = self._apply_task_transition(task, target)
            await session.commit()
            project_id = task.project_id
        await self._event_bus.publish(
            build_event(
                type=EventType.TASK_STATE_CHANGED,
                project_id=project_id,
                actor=actor,
                payload={
                    "task_id": task_id,
                    "previous_state": previous.value,
                    "new_state": target.value,
                },
                reason=reason,
            )
        )
        return project_id, previous

    async def _say(self, project_id: str, agent: AgentORM, task_id: str, text: str) -> None:
        await self._event_bus.publish(
            build_event(
                type=EventType.CONVERSATION_MESSAGE,
                project_id=project_id,
                actor=Actor(role="employee", id=agent.id, name=agent.name),
                payload={"text": text, "agent_id": agent.id, "task_id": task_id},
            )
        )

    async def _record_usage(
        self,
        project_id: str,
        task_id: str,
        agent: AgentORM,
        gateway: ProviderGateway,
        model_ref: str,
        usage: dict[str, int],
    ) -> None:
        if not usage:
            return
        await record_usage(
            self._session_factory,
            project_id=project_id,
            task_id=task_id,
            agent_id=agent.id,
            role=agent.role_key,
            provider=gateway.provider_name,
            model=await gateway.resolve_model(model_ref, _agent_model_override(agent)),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )

    async def _agents_for(self, project_id: str) -> dict[str, list[AgentORM]]:
        """Every Employee for this Company, grouped by Role -- a Role may
        hold more than one Employee (Sprint 10 §9.2), so this returns a
        list per role_key rather than assuming exactly one. *Which*
        Employee of a multi-Employee Role actually runs a stage is a
        separate policy question, resolved at the call site (Sprint 10
        Phase 3's resolver)."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(AgentORM).where(AgentORM.project_id == project_id)
            )
            rows = list(result.scalars().all())
        by_role: dict[str, list[AgentORM]] = {}
        for row in rows:
            by_role.setdefault(row.role_key, []).append(row)
        return by_role

    async def _resolve_agent(self, project_id: str, agents: dict[str, list[AgentORM]], role_key: str) -> AgentORM:
        """Sprint 10 §12: the pipeline's only call site for *which* Employee
        of `role_key` runs the upcoming stage -- selection policy itself
        lives in `employee_resolution.resolve_employee_for_role`, kept
        deterministic and Event-observable (§13, §14) so Sprint 12 can swap
        the policy without touching this call site."""
        selected, rule = resolve_employee_for_role(agents[role_key])

        now = datetime.now(timezone.utc)
        async with self._session_factory() as session:
            row = await session.get(AgentORM, selected.id)
            row.last_assigned_at = now
            await session.commit()
        selected.last_assigned_at = now

        rule_reason = (
            "was idle" if rule == "idle" else "no idle Employee was available; fell back across the whole Role"
        )
        await self._event_bus.publish(
            build_event(
                type=EventType.AGENT_RESOLVED,
                project_id=project_id,
                actor=SYSTEM_ACTOR,
                payload={"role_key": role_key, "agent_id": selected.id, "rule": rule},
                reason=f"Resolved {role_key} to {selected.name} ({rule_reason}, longest since assigned)",
            )
        )
        return selected

    async def _claim_agent(self, agent_id: str, reason: str) -> None:
        """IDLE -> ASSIGNED, waiting out a busy Employee instead of
        crashing with `InvalidTransition`. `_resolve_agent` can hand back
        an Employee that isn't actually idle yet by the time this runs --
        either its own fallback rule picked a busy Employee, or a
        concurrent pipeline claimed the same idle Employee first (see
        `_AGENT_CLAIM_TIMEOUT_SECONDS` above). Poll until the transition
        is legal; a genuinely stuck Employee still fails loud once the
        bounded wait runs out."""
        deadline = asyncio.get_event_loop().time() + _AGENT_CLAIM_TIMEOUT_SECONDS
        while True:
            try:
                await self._agent_runtime.transition(agent_id, AgentState.ASSIGNED, reason)
                return
            except InvalidTransition:
                if asyncio.get_event_loop().time() >= deadline:
                    raise
                await asyncio.sleep(_AGENT_CLAIM_POLL_SECONDS)

    async def _stream_say(
        self, project_id: str, agent: AgentORM, task_id: str, gateway: ProviderGateway, model_ref: str, **opts
    ) -> tuple[str, dict[str, int]]:
        """Stream one reply into the Meeting: publish a transient delta per
        chunk (so the UI can render token-by-token) and one persisted
        conversation.message once the reply is complete."""
        usage: dict[str, int] = {}
        buffer: list[str] = []
        actor = Actor(role="employee", id=agent.id, name=agent.name)
        async for chunk in gateway.stream(model_ref, usage=usage, agent_override=_agent_model_override(agent), **opts):
            buffer.append(chunk)
            await self._event_bus.publish_transient(
                build_event(
                    type=EventType.CONVERSATION_MESSAGE_DELTA,
                    project_id=project_id,
                    actor=actor,
                    payload={"text": chunk, "agent_id": agent.id, "task_id": task_id, "done": False},
                )
            )
        text = "".join(buffer)
        await self._event_bus.publish_transient(
            build_event(
                type=EventType.CONVERSATION_MESSAGE_DELTA,
                project_id=project_id,
                actor=actor,
                payload={"text": "", "agent_id": agent.id, "task_id": task_id, "done": True},
            )
        )
        await self._say(project_id, agent, task_id, text)
        return text, usage

    async def _run_role(
        self,
        agent: AgentORM,
        task: TaskSnapshot,
        gateway: ProviderGateway,
        model_ref: str,
        context: str,
        ceo_comment: str | None,
    ) -> tuple[str, dict[str, int]]:
        """Cycle one Employee through Assigned->Planning->Working->
        WaitingReview->Completed->Idle while it produces one message, and
        return the text it produced plus the usage it consumed.

        A cancel or an unhandled failure anywhere in this cycle is caught
        here (not by the caller) and always ends with the Employee back at
        Idle -- `_release_agent_to_idle` walks whatever multi-step path
        AGENT_TRANSITIONS requires from wherever this got interrupted
        (Sprint 9)."""
        project_id = task.project_id
        agent_token = agent_id_var.set(agent.id)
        project_token = project_id_var.set(project_id)
        try:
            try:
                await self._claim_agent(agent.id, f"Picked up mission '{task.title}'")
                await _pause()
                await self._agent_runtime.transition(agent.id, AgentState.PLANNING, "Reviewing the mission brief")
                await _pause()
                await self._agent_runtime.transition(agent.id, AgentState.WORKING, "Producing output")

                extra = f"\n\nCEO feedback to address: {ceo_comment}" if ceo_comment else ""
                text, usage = await self._stream_say(
                    project_id,
                    agent,
                    task.id,
                    gateway,
                    model_ref,
                    system=prompt_builder.build(
                        AgentProfile.model_validate(agent.profile), agent.role_key, task.deliverable_type
                    ),
                    messages=[{"role": "user", "content": f"Mission: {task.title}\n{task.description}{extra}"}],
                    task_title=task.title,
                    task_description=task.description,
                    context=context + extra,
                )
                await _pause()

                await self._agent_runtime.transition(agent.id, AgentState.WAITING_REVIEW, "Output ready for handoff")
                await _pause()
                await self._agent_runtime.transition(agent.id, AgentState.COMPLETED, "Handed off successfully")
                await self._agent_runtime.transition(agent.id, AgentState.IDLE, "Back to the bench")
                return text, usage
            except asyncio.CancelledError:
                await self._release_agent_to_idle(agent.id, "Mission cancelled")
                raise
            except Exception:
                await self._release_agent_to_idle(agent.id, "Mission failed")
                raise
        finally:
            agent_id_var.reset(agent_token)
            project_id_var.reset(project_token)

    async def _run_engineer_tool_loop(
        self,
        agent: AgentORM,
        task: TaskSnapshot,
        gateway: ProviderGateway,
        model_ref: str,
        role_spec: RoleSpec,
        context: str,
        ceo_comment: str | None,
    ) -> tuple[str, dict[str, int]]:
        """Tool-loop counterpart to `_run_role`, for `role_spec.harness ==
        "tool_loop"` Engineers on a code mission (Sprint 16 §7,
        DECISIONS.md #235). Same Employee state-cycle and cancel/failure
        release guarantee as `_run_role` -- the only difference is what
        happens between WORKING and WAITING_REVIEW: a bounded
        provider/tool loop (`agent_harness.orchestrator.run_tool_loop`)
        instead of one streamed reply.

        Unlike the one-shot path (which lands its FILE-block output on the
        branch only after the Employee finishes), the workspace/branch
        must exist *before* the loop starts here -- every tool call
        resolves against a committed branch ref (Rule #234)."""
        project_id = task.project_id
        branch_name = task.branch_name or self._branch_name_for(task.id)
        agent_token = agent_id_var.set(agent.id)
        project_token = project_id_var.set(project_id)
        try:
            try:
                await self._claim_agent(agent.id, f"Picked up mission '{task.title}'")
                await _pause()
                await self._agent_runtime.transition(agent.id, AgentState.PLANNING, "Reviewing the mission brief")
                await _pause()

                was_initialized = await self._workspace_manager.ensure_initialized(project_id)
                if was_initialized:
                    await self._event_bus.publish(
                        build_event(
                            type=EventType.WORKSPACE_INITIALIZED,
                            project_id=project_id,
                            actor=SYSTEM_ACTOR,
                            payload={},
                            reason="First code mission for this company; workspace repo created",
                        )
                    )
                await self._workspace_manager.create_branch(project_id, branch_name)
                # Sprint 17 §4.7/§8 (DECISIONS.md #239): captured once, right
                # after the branch exists and before any `apply_patch` commit --
                # `revert_last_patch`'s rollback floor for this attempt.
                branch_base_sha = await self._workspace_manager.head_sha(project_id, branch_name)

                await self._agent_runtime.transition(agent.id, AgentState.WORKING, "Producing output")

                profile = AgentProfile.model_validate(agent.profile)
                skill_template = SKILL_TEMPLATES_BY_KEY.get(profile.skill_template_key, GENERALIST)
                harness_enabled = settings.commander_harness_enabled
                permitted_tools = resolve_permitted_tools(
                    role=role_spec,
                    skill_template=skill_template,
                    stage_kind="produce",
                    harness_enabled=harness_enabled,
                    workspace_ready=True,
                )
                tool_context = ToolRunContext(
                    project_id=project_id,
                    task_id=task.id,
                    agent_id=agent.id,
                    repo_root=self._workspace_manager.repo_root(project_id),
                    branch_name=branch_name,
                    role=role_spec,
                    skill_template=skill_template,
                    stage_kind="produce",
                    harness_enabled=harness_enabled,
                    workspace_ready=True,
                    budget=HarnessBudget(stage=role_spec.key),
                    branch_base_sha=branch_base_sha,
                )
                loop_state = LoopState()

                extra = f"\n\nCEO feedback to address: {ceo_comment}" if ceo_comment else ""
                plan_block = f"\n\nPlan from the PM:\n{context}" if context else ""
                initial_user_message = f"Mission: {task.title}\n{task.description}{plan_block}{extra}"
                system = prompt_builder.build(
                    profile,
                    agent.role_key,
                    task.deliverable_type,
                    contract_override=TEMPLATE.tool_loop_contracts.get(role_spec.key),
                )

                async def _on_self_correction_triggered() -> None:
                    await self._event_bus.publish(
                        build_event(
                            type=EventType.SELF_CORRECTION_TRIGGERED,
                            project_id=project_id,
                            actor=Actor(role="employee", id=agent.id, name=agent.name),
                            payload={
                                "task_id": task.id,
                                "agent_id": agent.id,
                                "attempts_permitted": MAX_CORRECTION_ATTEMPTS,
                            },
                            reason="Engineer entered self-correction after a failed validation",
                        )
                    )

                result = await run_tool_loop(
                    context=tool_context,
                    gateway=gateway,
                    workspace_manager=self._workspace_manager,
                    sandbox_runner=self._sandbox_runner,
                    session_factory=self._session_factory,
                    model_ref=model_ref,
                    system=system,
                    initial_user_message=initial_user_message,
                    permitted_tools=permitted_tools,
                    loop_state=loop_state,
                    agent_override=_agent_model_override(agent),
                    on_self_correction_triggered=_on_self_correction_triggered,
                )
                if result.stop_reason == "employee_surrendered":
                    # Sprint 17 §4.5/§4.10 (DECISIONS.md #239): a legitimate,
                    # visible stop -- not a crash, not budget exhaustion. Raised
                    # here so `_run_pipeline`'s uniform raise -> catch -> fail-
                    # with-reason-code dispatch handles it exactly like every
                    # other structured tool-loop failure.
                    bounded_text, _ = bound_output(result.final_text or "")
                    raise EmployeeSurrenderedError(bounded_text)

                await self._say(project_id, agent, task.id, result.final_text)

                await _pause()
                await self._agent_runtime.transition(agent.id, AgentState.WAITING_REVIEW, "Output ready for handoff")
                await _pause()
                await self._agent_runtime.transition(agent.id, AgentState.COMPLETED, "Handed off successfully")
                await self._agent_runtime.transition(agent.id, AgentState.IDLE, "Back to the bench")
                return result.final_text, result.usage
            except asyncio.CancelledError:
                await self._release_agent_to_idle(agent.id, "Mission cancelled")
                raise
            except Exception:
                await self._release_agent_to_idle(agent.id, "Mission failed")
                raise
        finally:
            agent_id_var.reset(agent_token)
            project_id_var.reset(project_token)

    async def _release_agent_to_idle(self, agent_id: str, reason: str) -> None:
        """Force an Employee back onto the bench no matter which state a
        cancelled/failed mission left it in. AGENT_TRANSITIONS has no
        direct edge from most working states to Idle, so this walks the
        two-step path a state actually allows (Sprint 9).

        Also clears `current_task_id` (Sprint 10 §0.8): the state
        transition alone leaves it pointing at the mission that just
        ended, so a CEO message sent right after a cancel would still
        route to this Employee's stale mission. `recover_orphaned_tasks`
        (tasks/service.py) already clears this on its own recovery path;
        this brings the cancel path to the same behavior."""
        current = await self._agent_runtime.get_state(agent_id)
        if current != AgentState.IDLE:
            if current == AgentState.WAITING_REVIEW:
                await self._agent_runtime.transition(agent_id, AgentState.COMPLETED, reason)
            elif current not in (AgentState.COMPLETED, AgentState.FAILED):
                await self._agent_runtime.transition(agent_id, AgentState.FAILED, reason)
            current = await self._agent_runtime.get_state(agent_id)
            if current != AgentState.IDLE:
                await self._agent_runtime.transition(agent_id, AgentState.IDLE, reason)
        await self._agent_runtime.set_current_task(agent_id, None)

    async def _check_budget(self, task: TaskSnapshot, stage: str) -> None:
        """Mission budget guard (Rule #13, Sprint 9): checked before each
        pipeline stage starts. Exceeding any one cap raises rather than
        blocking directly, so the caller can decide when it's safe to
        transition the Mission to `blocked` (i.e. only once it's back in a
        state BLOCKED is reachable from)."""
        tokens, usd = await usage_for_task(self._session_factory, task.id)
        # SQLite (tests) hands back a naive datetime even though the column
        # is DateTime(timezone=True); Postgres (prod) always returns one
        # with tzinfo. Normalize rather than let the two backends disagree.
        created_at = task.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - created_at).total_seconds()
        if tokens > settings.commander_mission_max_tokens:
            raise BudgetExceededError("tokens", settings.commander_mission_max_tokens, tokens, stage)
        if usd > settings.commander_mission_max_usd:
            raise BudgetExceededError("usd", settings.commander_mission_max_usd, usd, stage)
        if elapsed > settings.commander_mission_max_seconds:
            raise BudgetExceededError("seconds", settings.commander_mission_max_seconds, elapsed, stage)

    async def _land_code_changes(
        self, task: TaskSnapshot, engineer_agent: AgentORM, deliverable: str
    ) -> tuple[str, dict | None]:
        """Parse the Engineer's FILE-block output and land it on the
        mission's branch (validated write + commit). Returns
        (change_summary, stats); stats is None if there were zero blocks
        or nothing valid to write -- the caller then falls back to
        treating this as a document mission rather than failing the
        pipeline (see parsing.parse_file_blocks). `stats["diff_text"]` is
        included for the Reviewer's context and must be stripped before
        persisting to TaskORM.code_stats."""
        files = parsing.parse_file_blocks(deliverable)
        if not files:
            return "", None

        project_id = task.project_id
        branch_name = task.branch_name or self._branch_name_for(task.id)

        was_initialized = await self._workspace_manager.ensure_initialized(project_id)
        if was_initialized:
            await self._event_bus.publish(
                build_event(
                    type=EventType.WORKSPACE_INITIALIZED,
                    project_id=project_id,
                    actor=SYSTEM_ACTOR,
                    payload={},
                    reason="First code mission for this company; workspace repo created",
                )
            )
        await self._workspace_manager.create_branch(project_id, branch_name)
        write_result = await self._workspace_manager.write_files(project_id, branch_name, files)
        if not write_result.written:
            return "", None

        commit_result = await self._workspace_manager.commit(
            project_id, branch_name, f"{task.title} (attempt {task.attempt})"
        )
        diff_text, truncated = await self._workspace_manager.diff(project_id, branch_name)
        if truncated:
            diff_text += "\n\n[diff truncated -- showing the first portion only]"
        change_summary = parsing.parse_change_summary(deliverable) or "No summary provided."
        stats = {
            "commit_sha": commit_result.commit_sha,
            "files_added": commit_result.files_added,
            "files_modified": commit_result.files_modified,
            "files_deleted": commit_result.files_deleted,
            "additions": commit_result.additions,
            "deletions": commit_result.deletions,
            "summary": change_summary,
        }

        async with self._session_factory() as session:
            row = await session.get(TaskORM, task.id)
            row.branch_name = branch_name
            row.code_stats = stats
            await session.commit()

        await self._event_bus.publish(
            build_event(
                type=EventType.CODE_CHANGED,
                project_id=project_id,
                actor=Actor(role="employee", id=engineer_agent.id, name=engineer_agent.name),
                payload={"branch_name": branch_name, **stats},
                reason=f"Engineer committed changes to '{branch_name}'",
            )
        )
        return change_summary, {**stats, "diff_text": diff_text}

    async def _land_tool_loop_changes(
        self, task: TaskSnapshot, engineer_agent: AgentORM, branch_name: str, deliverable: str
    ) -> tuple[str, dict | None]:
        """Counterpart to `_land_code_changes` for `harness == "tool_loop"`
        Engineers (Sprint 16 DECISIONS.md #235). `apply_patch` tool calls
        already wrote and committed files live during the loop
        (DECISIONS.md #234), so there is nothing left to parse/write/
        commit here -- this only computes the whole attempt's aggregate
        stats via `diff_stats()` (a multi-`apply_patch` attempt has no
        single `CommitResult`, #234) and persists/publishes exactly like
        `_land_code_changes` does. Returns stats=None if the branch has no
        diff against main at all (the Engineer only talked, never called
        `apply_patch`) -- the caller then treats this like a document
        mission, same as `_land_code_changes` returning stats=None for
        zero valid FILE blocks."""
        project_id = task.project_id
        diff_text, truncated = await self._workspace_manager.diff(project_id, branch_name)
        if not diff_text.strip():
            return deliverable, None
        if truncated:
            diff_text += "\n\n[diff truncated -- showing the first portion only]"

        commit_result = await self._workspace_manager.diff_stats(project_id, branch_name)
        change_summary = parsing.parse_change_summary(deliverable) or "No summary provided."
        stats = {
            "commit_sha": commit_result.commit_sha,
            "files_added": commit_result.files_added,
            "files_modified": commit_result.files_modified,
            "files_deleted": commit_result.files_deleted,
            "additions": commit_result.additions,
            "deletions": commit_result.deletions,
            "summary": change_summary,
        }

        async with self._session_factory() as session:
            row = await session.get(TaskORM, task.id)
            row.branch_name = branch_name
            row.code_stats = stats
            await session.commit()

        await self._event_bus.publish(
            build_event(
                type=EventType.CODE_CHANGED,
                project_id=project_id,
                actor=Actor(role="employee", id=engineer_agent.id, name=engineer_agent.name),
                payload={"branch_name": branch_name, **stats},
                reason=f"Engineer committed changes to '{branch_name}' via the Agent Harness tool loop",
            )
        )
        return change_summary, {**stats, "diff_text": diff_text}

    async def _run_checks(
        self, task: TaskSnapshot, branch_name: str
    ) -> tuple[str, list[dict] | None]:
        """Run every template-detected check (Sprint 6) against the
        mission branch's files, between the Engineer's commit and the
        Reviewer's turn. Returns (summary_for_reviewer, results); results
        is None when execution is disabled for this company or no check's
        `detect_globs` matched anything -- in both cases nothing runs and
        no execution.* events are published, keeping the Timeline quiet
        for missions execution never applies to. Sandbox trouble (no
        Docker, no image, timeout) never raises here -- `run_check`
        always returns a `could_not_run` CheckResult (see
        core/interfaces/sandbox.py), so a flaky/absent sandbox can only
        ever show up as a check result, never crash the pipeline."""
        project_id = task.project_id
        if not await get_execution_enabled(self._session_factory, project_id):
            return "", None

        tree = await self._workspace_manager.list_tree(project_id, ref=branch_name)
        paths = [entry.path for entry in tree]
        matched = detect_checks(paths, TEMPLATE.checks)
        if not matched:
            return "", None

        files = {
            path: await self._workspace_manager.read_file(project_id, path, ref=branch_name)
            for path in paths
        }

        await self._event_bus.publish(
            build_event(
                type=EventType.EXECUTION_STARTED,
                project_id=project_id,
                actor=SYSTEM_ACTOR,
                payload={"task_id": task.id, "check_names": [c.name for c in matched]},
                reason="Running automated checks before Reviewer audit",
            )
        )

        results = [
            await self._sandbox_runner.run_check(check.name, files, list(check.command))
            for check in matched
        ]
        passed_count = sum(1 for r in results if r.status == "passed")
        total_count = len(results)
        result_dicts = [
            {"name": r.name, "status": r.status, "duration_seconds": r.duration_seconds, "output": r.output}
            for r in results
        ]

        await self._event_bus.publish(
            build_event(
                type=EventType.EXECUTION_COMPLETED,
                project_id=project_id,
                actor=SYSTEM_ACTOR,
                payload={
                    "task_id": task.id,
                    "results": result_dicts,
                    "passed_count": passed_count,
                    "total_count": total_count,
                },
                reason=f"{passed_count}/{total_count} checks passed",
            )
        )

        summary_lines = [f"Automated checks: {passed_count}/{total_count} passed."]
        for r in results:
            if r.status != "passed":
                summary_lines.append(f"- {r.name} ({r.status}): {r.output[:500]}")
        return "\n".join(summary_lines), result_dicts

    async def _run_pipeline(
        self, task_id: str, resume_from: int, ceo_comment: str | None = None
    ) -> None:
        """Iterate `TEMPLATE.pipeline` from `resume_from` (a stage index,
        not a role_key -- Sprint 9, since the same `kind` can repeat)
        rather than three hardcoded PM/Engineer/Reviewer steps. Each
        stage's `kind` selects its event shape and side effects; a
        "review" stage is always pipeline-terminal (it creates the CEO
        Decision), matching the current template's single trailing
        audit step."""
        try:
            async with self._session_factory() as session:
                task_row = await session.get(TaskORM, task_id)
                task = TaskSnapshot.from_orm(task_row)
            project_id = task.project_id
            title = task.title

            agents = await self._agents_for(project_id)
            gateway = await self._gateway_for(project_id)

            if resume_from == 0:
                await self._set_task_state(
                    task_id, TaskState.IN_PROGRESS, "Mission picked up by the Department", SYSTEM_ACTOR
                )

            context = ""
            deliverable = ""
            change_summary = ""
            code_stats: dict | None = None

            for index, stage in enumerate(TEMPLATE.pipeline):
                if index < resume_from:
                    continue

                if stage.kind == "review":
                    await self._set_task_state(
                        task_id, TaskState.IN_REVIEW, "Handing off for review", SYSTEM_ACTOR
                    )

                agent = await self._resolve_agent(project_id, agents, stage.role_key)
                role_spec = TEMPLATE.roles_by_key[stage.role_key]
                model_ref = role_spec.model_ref
                role_title = role_spec.title
                await self._check_budget(task, stage.role_key)

                if stage.kind == "plan":
                    await self._event_bus.publish(
                        build_event(
                            type=EventType.TASK_STARTED,
                            project_id=project_id,
                            actor=Actor(role="employee", id=agent.id, name=agent.name),
                            payload={"task_id": task_id, "agent_id": agent.id},
                            reason=f"{role_title} started planning '{title}'",
                        )
                    )
                    context, usage = await self._run_role(agent, task, gateway, model_ref, context, None)
                    await self._record_usage(project_id, task_id, agent, gateway, model_ref, usage)

                elif stage.kind == "produce":
                    await self._event_bus.publish(
                        build_event(
                            type=EventType.CODING_STARTED,
                            project_id=project_id,
                            actor=Actor(role="employee", id=agent.id, name=agent.name),
                            payload={"agent_id": agent.id, "task_id": task_id},
                            reason=f"{role_title} began building the deliverable",
                        )
                    )

                    # Sprint 16 §7 (DECISIONS.md #235): a "tool_loop" harness
                    # Role on a code mission runs the bounded Agent Harness
                    # tool loop instead of one-shot FILE-block output; every
                    # other case (document missions, any "one_shot" Role) is
                    # untouched. Branches on `role_spec.harness` (Role-owned
                    # data), never a hardcoded role name (Rule #16).
                    if role_spec.harness == "tool_loop" and task.deliverable_type == "code":
                        deliverable, usage = await self._run_engineer_tool_loop(
                            agent, task, gateway, model_ref, role_spec, context, ceo_comment
                        )
                        await self._record_usage(project_id, task_id, agent, gateway, model_ref, usage)
                        ceo_comment = None

                        branch_name = task.branch_name or self._branch_name_for(task.id)
                        task = dataclasses.replace(task, branch_name=branch_name)
                        change_summary, code_stats = await self._land_tool_loop_changes(
                            task, agent, branch_name, deliverable
                        )
                    else:
                        deliverable, usage = await self._run_role(
                            agent, task, gateway, model_ref, context, ceo_comment
                        )
                        await self._record_usage(project_id, task_id, agent, gateway, model_ref, usage)
                        ceo_comment = None  # only the resumed stage gets the CEO's feedback

                        change_summary, code_stats = "", None
                        if stage.lands_code and task.deliverable_type == "code":
                            change_summary, code_stats = await self._land_code_changes(
                                task, agent, deliverable
                            )
                            if code_stats is not None:
                                branch_name = task.branch_name or self._branch_name_for(task.id)
                                task = dataclasses.replace(task, branch_name=branch_name)

                    context = deliverable
                    if code_stats is not None:
                        context = f"{change_summary}\n\n{code_stats['diff_text']}"
                        code_stats = {k: v for k, v in code_stats.items() if k != "diff_text"}
                        if stage.runs_checks:
                            check_summary, check_results = await self._run_checks(task, task.branch_name)
                            if check_results is not None:
                                context = f"{context}\n\n{check_summary}"
                                async with self._session_factory() as session:
                                    row = await session.get(TaskORM, task_id)
                                    row.check_results = check_results
                                    await session.commit()

                elif stage.kind == "review":
                    await self._event_bus.publish(
                        build_event(
                            type=EventType.REVIEW_STARTED,
                            project_id=project_id,
                            actor=Actor(role="employee", id=agent.id, name=agent.name),
                            payload={"task_id": task_id, "reviewer_agent_id": agent.id},
                            reason=f"{role_title} began the audit",
                        )
                    )
                    audit, usage = await self._run_role(agent, task, gateway, model_ref, context, None)
                    await self._record_usage(project_id, task_id, agent, gateway, model_ref, usage)
                    outcome = parsing.parse_verdict(audit)
                    sections = parsing.parse_decision_sections(audit)
                    await self._event_bus.publish(
                        build_event(
                            type=EventType.REVIEW_COMPLETED,
                            project_id=project_id,
                            actor=Actor(role="employee", id=agent.id, name=agent.name),
                            payload={"task_id": task_id, "outcome": outcome, "sections": sections},
                            reason=f"{role_title} verdict: {outcome}",
                        )
                    )

                    async with self._session_factory() as session:
                        task_row = await session.get(TaskORM, task_id)
                        task_row.result_markdown = change_summary if code_stats is not None else deliverable
                        self._apply_task_transition(task_row, TaskState.PENDING_APPROVAL)
                        approval = ApprovalORM(
                            project_id=project_id,
                            task_id=task_id,
                            subject="task_review",
                            status="pending",
                            reviewer_agent_id=agent.id,
                            reviewer_name=agent.name,
                            sections=sections,
                            raw_summary=audit,
                        )
                        session.add(approval)
                        await session.commit()
                        await session.refresh(approval)
                        approval_id = approval.id

                    await self._event_bus.publish(
                        build_event(
                            type=EventType.TASK_STATE_CHANGED,
                            project_id=project_id,
                            actor=SYSTEM_ACTOR,
                            payload={
                                "task_id": task_id,
                                "previous_state": TaskState.IN_REVIEW.value,
                                "new_state": TaskState.PENDING_APPROVAL.value,
                            },
                            reason="Reviewer finished; needs a CEO Decision",
                        )
                    )
                    await self._event_bus.publish(
                        build_event(
                            type=EventType.APPROVAL_REQUESTED,
                            project_id=project_id,
                            actor=SYSTEM_ACTOR,
                            payload={"approval_id": approval_id, "task_id": task_id, "subject": "task_review"},
                            reason=f"'{title}' is ready for a CEO Decision ({role_title} verdict: {outcome})",
                        )
                    )
        except asyncio.CancelledError:
            logger.info("pipeline for task %s cancelled", task_id)
            reason = self._cancel_reasons.pop(task_id, "Cancelled by CEO")
            await self._finish_task(task_id, TaskState.CANCELLED, reason, EventType.TASK_CANCELLED)
            raise
        except BudgetExceededError as exc:
            logger.info("mission %s blocked: %s", task_id, exc)
            await self._block_task_on_budget(task_id, exc)
        except SelfCorrectionExhaustedError as exc:
            logger.info("mission %s failed: self-correction exhausted: %s", task_id, exc)
            await self._fail_task_with_reason_code(task_id, "self_correction_exhausted", str(exc))
        except EmployeeSurrenderedError as exc:
            logger.info("mission %s failed: employee surrendered: %s", task_id, exc)
            await self._fail_task_with_reason_code(task_id, "employee_surrendered", str(exc))
        except Exception as exc:  # noqa: BLE001 - convert any pipeline failure into TaskFailed
            logger.exception("workflow pipeline failed for task %s", task_id)
            await self._fail_task(task_id, str(exc))

    async def _block_task_on_budget(self, task_id: str, exc: BudgetExceededError) -> None:
        async with self._session_factory() as session:
            task_row = await session.get(TaskORM, task_id)
            previous = self._apply_task_transition(task_row, TaskState.BLOCKED)
            await session.commit()
            project_id = task_row.project_id
        await self._event_bus.publish(
            build_event(
                type=EventType.BUDGET_EXCEEDED,
                project_id=project_id,
                actor=SYSTEM_ACTOR,
                payload={
                    "task_id": task_id,
                    "limit_kind": exc.limit_kind,
                    "limit_value": exc.limit_value,
                    "observed_value": exc.observed_value,
                    "stage": exc.stage,
                },
                reason=str(exc),
            )
        )
        await self._event_bus.publish(
            build_event(
                type=EventType.TASK_STATE_CHANGED,
                project_id=project_id,
                actor=SYSTEM_ACTOR,
                payload={
                    "task_id": task_id,
                    "previous_state": previous.value,
                    "new_state": TaskState.BLOCKED.value,
                },
                reason=f"Budget guard blocked the mission before '{exc.stage}'",
            )
        )

    async def _fail_task(self, task_id: str, reason: str) -> None:
        async with self._session_factory() as session:
            task = await session.get(TaskORM, task_id)
            if task is None:
                return
            current = TaskState(task.state)
            if TaskState.FAILED in TASK_TRANSITIONS.get(current, set()):
                task.state = TaskState.FAILED.value
            project_id = task.project_id
            await session.commit()
        await self._event_bus.publish(
            build_event(
                type=EventType.TASK_FAILED,
                project_id=project_id,
                actor=SYSTEM_ACTOR,
                payload={"task_id": task_id},
                reason=reason,
            )
        )

    async def _fail_task_with_reason_code(self, task_id: str, reason_code: str, reason: str) -> None:
        """Sprint 17 §4.10/§8 (DECISIONS.md #239): same transition as
        `_fail_task`, additionally carrying a structured `reason_code` on
        the `TASK_FAILED` payload -- additive, so every pre-Sprint-17
        consumer of this payload still validates unchanged."""
        async with self._session_factory() as session:
            task = await session.get(TaskORM, task_id)
            if task is None:
                return
            current = TaskState(task.state)
            if TaskState.FAILED in TASK_TRANSITIONS.get(current, set()):
                task.state = TaskState.FAILED.value
            project_id = task.project_id
            await session.commit()
        await self._event_bus.publish(
            build_event(
                type=EventType.TASK_FAILED,
                project_id=project_id,
                actor=SYSTEM_ACTOR,
                payload={"task_id": task_id, "reason_code": reason_code},
                reason=reason,
            )
        )

    async def _mark_pending_approval(
        self, task_id: str, status: str, comment: str | None
    ) -> str | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(ApprovalORM)
                .where(ApprovalORM.task_id == task_id, ApprovalORM.status == "pending")
                .order_by(ApprovalORM.created_at.desc())
            )
            approval = result.scalars().first()
            if not approval:
                return None
            approval.status = status
            approval.comment = comment
            await session.commit()
            return approval.id

    async def _finish_task(
        self,
        task_id: str,
        target: TaskState,
        comment: str | None,
        narrative_type: EventType,
    ) -> None:
        async with self._session_factory() as session:
            task = await session.get(TaskORM, task_id)
            self._apply_task_transition(task, target)
            await session.commit()
            project_id, title = task.project_id, task.title

        approval_status = "approved" if target == TaskState.COMPLETED else "rejected"
        approval_event_type = (
            EventType.APPROVAL_GRANTED if approval_status == "approved" else EventType.APPROVAL_REJECTED
        )
        approval_id = await self._mark_pending_approval(task_id, approval_status, comment)

        if approval_id:
            await self._event_bus.publish(
                build_event(
                    type=approval_event_type,
                    project_id=project_id,
                    actor=CEO_ACTOR,
                    payload={"approval_id": approval_id},
                    reason=comment,
                )
            )
        await self._event_bus.publish(
            build_event(
                type=narrative_type,
                project_id=project_id,
                actor=CEO_ACTOR,
                payload={"task_id": task_id},
                reason=comment or f"CEO Decision on '{title}'",
            )
        )

    async def _approve_task(self, task_id: str, comment: str | None) -> None:
        """CEO approved. Document missions complete outright; code missions
        merge the mission branch to main first -- a merge conflict blocks
        the mission (TaskState.BLOCKED) rather than completing it, with no
        auto-resolution (see docs/DECISIONS.md 'Sprint 5')."""
        async with self._session_factory() as session:
            task = await session.get(TaskORM, task_id)
            project_id = task.project_id
            deliverable_type, branch_name = task.deliverable_type, task.branch_name

        if deliverable_type == "code" and branch_name:
            try:
                commit_sha = await self._workspace_manager.merge(project_id, branch_name)
            except WorkspaceConflictError as exc:
                await self._block_task_on_merge_failure(task_id, comment, str(exc))
                return
            await self._event_bus.publish(
                build_event(
                    type=EventType.BRANCH_MERGED,
                    project_id=project_id,
                    actor=CEO_ACTOR,
                    payload={"branch_name": branch_name, "commit_sha": commit_sha},
                    reason=f"CEO approved; '{branch_name}' merged to main",
                )
            )
        await self._finish_task(task_id, TaskState.COMPLETED, comment, EventType.TASK_COMPLETED)

    async def _block_task_on_merge_failure(
        self, task_id: str, comment: str | None, error: str
    ) -> None:
        async with self._session_factory() as session:
            task = await session.get(TaskORM, task_id)
            previous = self._apply_task_transition(task, TaskState.BLOCKED)
            await session.commit()
            project_id = task.project_id

        approval_id = await self._mark_pending_approval(task_id, "approved", comment)
        if approval_id:
            await self._event_bus.publish(
                build_event(
                    type=EventType.APPROVAL_GRANTED,
                    project_id=project_id,
                    actor=CEO_ACTOR,
                    payload={"approval_id": approval_id},
                    reason=comment,
                )
            )
        await self._event_bus.publish(
            build_event(
                type=EventType.TASK_STATE_CHANGED,
                project_id=project_id,
                actor=SYSTEM_ACTOR,
                payload={
                    "task_id": task_id,
                    "previous_state": previous.value,
                    "new_state": TaskState.BLOCKED.value,
                },
                reason=f"CEO approved, but merge to main failed: {error}",
            )
        )
