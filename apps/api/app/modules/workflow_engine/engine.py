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
from ...core.errors import WorkspaceConflictError
from ...core.events import Actor, EventType, build_event
from ...core.interfaces.agent_runtime import AgentRuntime
from ...core.interfaces.event_bus import EventBus
from ...core.interfaces.provider_gateway import ProviderGateway
from ...core.interfaces.sandbox import SandboxRunner
from ...core.interfaces.workflow_engine import WorkflowEngine
from ...core.interfaces.workspace_manager import WorkspaceManager
from ...core.lifecycle.agent_states import AgentState
from ...core.lifecycle.state_machine import transition
from ...core.lifecycle.task_states import TASK_TRANSITIONS, TaskState
from ...core.secrets import SecretsProvider
from ...core.config import settings
from ...templates import TEMPLATE
from .. import prompt_builder
from ..costs import record_usage
from ..model_registry import RECOMMENDED_PROVIDER
from ..provider_gateway import build_gateway
from ..sandbox import detect_checks, get_execution_enabled
from . import parsing

logger = logging.getLogger("commander.workflow_engine")

SYSTEM_ACTOR = Actor(role="system", id="system", name="Commander")
CEO_ACTOR = Actor(role="ceo", id="ceo", name="CEO")

# The pipeline's fixed shape (PM plans -> Engineer builds -> Reviewer
# audits) is concrete engine logic, not template-driven -- only the role
# *identity* (key, model ref) comes from the template (§10.6). See
# docs/DECISIONS.md "Sprint 4.7".
_PM, _ENGINEER, _REVIEWER = TEMPLATE.roles


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

    # --- public API -----------------------------------------------------

    async def start_task(self, task_id: str) -> None:
        asyncio.create_task(self._run_pipeline(task_id, resume_from=_PM.key))

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
            asyncio.create_task(
                self._run_pipeline(task_id, resume_from=_ENGINEER.key, ceo_comment=comment)
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
            system=prompt_builder.build(
                AgentProfile.model_validate(agent.profile), agent.role, task.deliverable_type
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

    async def _land_code_changes(
        self, task: TaskORM, engineer_agent: AgentORM, deliverable: str
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

    async def _run_checks(
        self, task: TaskORM, branch_name: str
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
        self, task_id: str, resume_from: str, ceo_comment: str | None = None
    ) -> None:
        try:
            async with self._session_factory() as session:
                task = await session.get(TaskORM, task_id)
                project_id = task.project_id
                title = task.title

            agents = await self._agents_for(project_id)
            gateway = await self._gateway_for(project_id)

            if resume_from == _PM.key:
                await self._set_task_state(
                    task_id, TaskState.IN_PROGRESS, "PM began planning", SYSTEM_ACTOR
                )
                pm_agent = agents[_PM.key]
                await self._event_bus.publish(
                    build_event(
                        type=EventType.TASK_STARTED,
                        project_id=project_id,
                        actor=Actor(role="employee", id=pm_agent.id, name=pm_agent.name),
                        payload={"task_id": task_id, "agent_id": pm_agent.id},
                        reason=f"PM started planning '{title}'",
                    )
                )
                plan, pm_usage = await self._run_role(pm_agent, task, gateway, _PM.model_ref, "", None)
                await self._record_usage(project_id, task_id, pm_agent, gateway, _PM.model_ref, pm_usage)
            else:
                plan, pm_usage = "", {}

            engineer_agent = agents[_ENGINEER.key]
            await self._event_bus.publish(
                build_event(
                    type=EventType.CODING_STARTED,
                    project_id=project_id,
                    actor=Actor(role="employee", id=engineer_agent.id, name=engineer_agent.name),
                    payload={"agent_id": engineer_agent.id, "task_id": task_id},
                    reason="Engineer began building the deliverable",
                )
            )
            deliverable, engineer_usage = await self._run_role(
                engineer_agent, task, gateway, _ENGINEER.model_ref, plan, ceo_comment
            )
            await self._record_usage(
                project_id, task_id, engineer_agent, gateway, _ENGINEER.model_ref, engineer_usage
            )

            reviewer_context = deliverable
            change_summary = ""
            code_stats: dict | None = None
            if task.deliverable_type == "code":
                change_summary, code_stats = await self._land_code_changes(
                    task, engineer_agent, deliverable
                )
                if code_stats is not None:
                    reviewer_context = f"{change_summary}\n\n{code_stats['diff_text']}"
                    code_stats = {k: v for k, v in code_stats.items() if k != "diff_text"}

                    branch_name = task.branch_name or self._branch_name_for(task.id)
                    check_summary, check_results = await self._run_checks(task, branch_name)
                    if check_results is not None:
                        reviewer_context = f"{reviewer_context}\n\n{check_summary}"
                        async with self._session_factory() as session:
                            row = await session.get(TaskORM, task_id)
                            row.check_results = check_results
                            await session.commit()

            await self._set_task_state(
                task_id, TaskState.IN_REVIEW, "Engineer finished; handing to Reviewer", SYSTEM_ACTOR
            )
            reviewer_agent = agents[_REVIEWER.key]
            await self._event_bus.publish(
                build_event(
                    type=EventType.REVIEW_STARTED,
                    project_id=project_id,
                    actor=Actor(role="employee", id=reviewer_agent.id, name=reviewer_agent.name),
                    payload={"task_id": task_id, "reviewer_agent_id": reviewer_agent.id},
                    reason="Reviewer began the audit",
                )
            )
            audit, reviewer_usage = await self._run_role(
                reviewer_agent, task, gateway, _REVIEWER.model_ref, reviewer_context, None
            )
            await self._record_usage(
                project_id, task_id, reviewer_agent, gateway, _REVIEWER.model_ref, reviewer_usage
            )
            outcome = parsing.parse_verdict(audit)
            sections = parsing.parse_decision_sections(audit)
            await self._event_bus.publish(
                build_event(
                    type=EventType.REVIEW_COMPLETED,
                    project_id=project_id,
                    actor=Actor(role="employee", id=reviewer_agent.id, name=reviewer_agent.name),
                    payload={"task_id": task_id, "outcome": outcome},
                    reason=f"Reviewer verdict: {outcome}",
                )
            )

            async with self._session_factory() as session:
                task = await session.get(TaskORM, task_id)
                task.result_markdown = change_summary if code_stats is not None else deliverable
                self._apply_task_transition(task, TaskState.PENDING_APPROVAL)
                approval = ApprovalORM(
                    project_id=project_id,
                    task_id=task_id,
                    subject="task_review",
                    status="pending",
                    reviewer_agent_id=reviewer_agent.id,
                    reviewer_name=reviewer_agent.name,
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
