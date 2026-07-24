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
import logging
import random

from sqlalchemy import select

from ...core.contracts import AgentProfile
from ...core.db_models import AgentORM, ApprovalORM, TaskORM
from ...core.events import Actor, EventType, build_event
from ...core.interfaces.agent_runtime import AgentRuntime
from ...core.interfaces.event_bus import EventBus
from ...core.interfaces.provider_gateway import ProviderGateway
from ...core.interfaces.workflow_engine import WorkflowEngine
from ...core.lifecycle.agent_states import AgentState
from ...core.lifecycle.state_machine import transition
from ...core.lifecycle.task_states import TASK_TRANSITIONS, TaskState
from ...core.secrets import SecretsProvider
from .. import prompt_builder
from ..costs import record_usage
from ..model_registry import RECOMMENDED_PROVIDER
from ..provider_gateway import build_gateway

logger = logging.getLogger("commander.workflow_engine")

SYSTEM_ACTOR = Actor(role="system", id="system", name="Commander")
CEO_ACTOR = Actor(role="ceo", id="ceo", name="CEO")


def _pause() -> "asyncio.Future[None]":
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
    ) -> None:
        self._session_factory = session_factory
        self._event_bus = event_bus
        self._agent_runtime = agent_runtime
        self._secrets = secrets

    # --- public API -----------------------------------------------------

    async def start_task(self, task_id: str) -> None:
        asyncio.create_task(self._run_pipeline(task_id, resume_from="pm"))

    async def resume_after_decision(
        self, task_id: str, decision: str, comment: str | None
    ) -> None:
        if decision == "approve":
            await self._finish_task(task_id, TaskState.COMPLETED, comment, EventType.TASK_COMPLETED)
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
            asyncio.create_task(
                self._run_pipeline(task_id, resume_from="engineer", ceo_comment=comment)
            )

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
            role=agent.role,
            provider=gateway.provider_name,
            model=await gateway.resolve_model(model_ref, _agent_model_override(agent)),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )

    async def _agents_for(self, project_id: str) -> dict[str, AgentORM]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(AgentORM).where(AgentORM.project_id == project_id)
            )
            rows = list(result.scalars().all())
        return {row.role: row for row in rows}

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
        task: TaskORM,
        gateway: ProviderGateway,
        model_ref: str,
        context: str,
        ceo_comment: str | None,
    ) -> tuple[str, dict[str, int]]:
        """Cycle one Employee through Assigned->Planning->Working->
        WaitingReview->Completed->Idle while it produces one message, and
        return the text it produced plus the usage it consumed."""
        project_id = task.project_id
        await self._agent_runtime.transition(agent.id, AgentState.ASSIGNED, f"Picked up mission '{task.title}'")
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
            system=prompt_builder.build(AgentProfile.model_validate(agent.profile), agent.role),
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

    async def _run_pipeline(
        self, task_id: str, resume_from: str, ceo_comment: str | None = None
    ) -> None:
        try:
            async with self._session_factory() as session:
                task = await session.get(TaskORM, task_id)
                project_id = task.project_id
                title = task.title

            agents = await self._agents_for(project_id)
            gateway = await self._gateway_for(project_id)

            if resume_from == "pm":
                await self._set_task_state(
                    task_id, TaskState.IN_PROGRESS, "PM began planning", SYSTEM_ACTOR
                )
                await self._event_bus.publish(
                    build_event(
                        type=EventType.TASK_STARTED,
                        project_id=project_id,
                        actor=Actor(role="employee", id=agents["pm"].id, name=agents["pm"].name),
                        payload={"task_id": task_id, "agent_id": agents["pm"].id},
                        reason=f"PM started planning '{title}'",
                    )
                )
                plan, pm_usage = await self._run_role(agents["pm"], task, gateway, "planner-default", "", None)
                await self._record_usage(project_id, task_id, agents["pm"], gateway, "planner-default", pm_usage)
            else:
                plan, pm_usage = "", {}

            await self._event_bus.publish(
                build_event(
                    type=EventType.CODING_STARTED,
                    project_id=project_id,
                    actor=Actor(role="employee", id=agents["engineer"].id, name=agents["engineer"].name),
                    payload={"agent_id": agents["engineer"].id, "task_id": task_id},
                    reason="Engineer began building the deliverable",
                )
            )
            deliverable, engineer_usage = await self._run_role(
                agents["engineer"], task, gateway, "builder-default", plan, ceo_comment
            )
            await self._record_usage(
                project_id, task_id, agents["engineer"], gateway, "builder-default", engineer_usage
            )

            await self._set_task_state(
                task_id, TaskState.IN_REVIEW, "Engineer finished; handing to Reviewer", SYSTEM_ACTOR
            )
            await self._event_bus.publish(
                build_event(
                    type=EventType.REVIEW_STARTED,
                    project_id=project_id,
                    actor=Actor(role="employee", id=agents["reviewer"].id, name=agents["reviewer"].name),
                    payload={"task_id": task_id, "reviewer_agent_id": agents["reviewer"].id},
                    reason="Reviewer began the audit",
                )
            )
            audit, reviewer_usage = await self._run_role(
                agents["reviewer"], task, gateway, "reviewer-default", deliverable, None
            )
            await self._record_usage(
                project_id, task_id, agents["reviewer"], gateway, "reviewer-default", reviewer_usage
            )
            outcome = "changes_requested" if "changes requested" in audit.lower() else "approved"
            await self._event_bus.publish(
                build_event(
                    type=EventType.REVIEW_COMPLETED,
                    project_id=project_id,
                    actor=Actor(role="employee", id=agents["reviewer"].id, name=agents["reviewer"].name),
                    payload={"task_id": task_id, "outcome": outcome},
                    reason=f"Reviewer verdict: {outcome}",
                )
            )

            async with self._session_factory() as session:
                task = await session.get(TaskORM, task_id)
                task.result_markdown = deliverable
                self._apply_task_transition(task, TaskState.PENDING_APPROVAL)
                approval = ApprovalORM(
                    project_id=project_id,
                    task_id=task_id,
                    subject="task_review",
                    status="pending",
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
                    reason=f"'{title}' is ready for a CEO Decision (Reviewer verdict: {outcome})",
                )
            )
        except Exception as exc:  # noqa: BLE001 - convert any pipeline failure into TaskFailed
            logger.exception("workflow pipeline failed for task %s", task_id)
            await self._fail_task(task_id, str(exc))

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

        approval_event_type = (
            EventType.APPROVAL_GRANTED if target == TaskState.COMPLETED else EventType.APPROVAL_REJECTED
        )
        async with self._session_factory() as session:
            result = await session.execute(
                select(ApprovalORM)
                .where(ApprovalORM.task_id == task_id, ApprovalORM.status == "pending")
                .order_by(ApprovalORM.created_at.desc())
            )
            approval = result.scalars().first()
            if approval:
                approval.status = "approved" if target == TaskState.COMPLETED else "rejected"
                approval.comment = comment
                await session.commit()
                approval_id = approval.id
            else:
                approval_id = None

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
