"""Sprint 12: the PM<->CTO planning orchestrator (brief §5.1).

Deliberately outside `workflow_engine` (Rule #1/#5 -- planning is a
different pipeline with a different bounded-turn shape, not a fourth
`StageSpec.kind`; see docs/DECISIONS.md #149). `PlanningOrchestrator` is
built fresh per call from `session_factory`/`event_bus`/`agent_runtime`/
`secrets` -- the same "no dedicated DI singleton" shape `build_gateway()`
already has -- rather than a long-lived registry like
`CommanderWorkflowEngine._running` (PROGRESS.txt Phase 0 design decision
0.8). That's possible because every planning "turn burst" (`start`,
`resume_after_clarification`, `submit_revision`) runs to completion inside
one awaited call: nothing keeps running between calls the way a Mission's
background asyncio.Task does, so there is nothing to track across calls.

Turn-kind dispatch (`_role_for_kind`, the `while` loop in `_run`) branches
on the *turn kind* string (`"pm_analysis"`, `"cto_review"`, ...), never on
a role key literal -- these are workflow-stage labels, the same Rule #16
exception `StageSpec.kind` already relies on ("stage kinds ... allowed to
drive behavior because they represent workflow semantics rather than
organizational role identities"). The one place an actual role key is
needed (`TEMPLATE.planning_pm_role_key` / `planning_cto_role_key`) is
template data, never a literal `"pm"`/`"cto"` comparison.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ...core.contracts import AgentProfile
from ...core.db_models import (
    ActiveSpecificationLockORM,
    AgentORM,
    ProjectORM,
    SpecificationORM,
    SpecificationTurnORM,
    SpecificationVersionORM,
)
from ...core.errors import (
    ActivePlanningExistsError,
    CTOVacantError,
    MalformedProviderOutputError,
    PlanningTurnBudgetExhaustedError,
)
from ...core.events import Actor, EventType, build_event
from ...core.interfaces.agent_runtime import AgentRuntime
from ...core.interfaces.event_bus import EventBus
from ...core.interfaces.provider_gateway import ProviderGateway
from ...core.lifecycle.agent_states import AgentState
from ...core.lifecycle.specification_states import SPECIFICATION_TRANSITIONS, SpecificationStatus
from ...core.lifecycle.state_machine import transition
from ...core.secrets import SecretsProvider
from ...templates import TEMPLATE
from .. import prompt_builder
from ..memory import CATEGORIES as MEMORY_CATEGORIES
from ..memory import RecallRequest, RecalledMemory
from ..memory import recall as memory_recall
from ..model_registry import RECOMMENDED_PROVIDER
from ..provider_gateway import build_gateway
from ..workflow_engine import resolve_employee_for_role

logger = logging.getLogger("commander.planning")

SYSTEM_ACTOR = Actor(role="system", id="system", name="Commander")
CEO_ACTOR = Actor(role="ceo", id="ceo", name="CEO")

# Sprint 12 §4.3 / docs/DECISIONS.md #200: 6 turns lifetime per
# Specification, cumulative across revision rounds. Counts only PM/CTO
# ("employee") turns -- §4.3's own definition ("a turn is one persisted PM
# or CTO contribution") excludes the CEO's own clarification-answer row.
MAX_PLANNING_TURNS = 6
# Sprint 12 §4.12: bounded retry for malformed structured output. 2 total
# attempts (1 retry) is enough to absorb one-off formatting slips without
# turning a bad response into an unbounded loop.
MAX_MALFORMED_ATTEMPTS = 2


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _agent_model_override(agent: AgentORM) -> str | None:
    return agent.profile.get("model_ref")


def _role_for_kind(kind: str) -> str:
    if kind in ("cto_review", "cto_followup_answer"):
        return TEMPLATE.planning_cto_role_key
    return TEMPLATE.planning_pm_role_key


# --- structured-output parsing/validation -----------------------------------


def _parse_json(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped[:4].lower() == "json":
            stripped = stripped[4:]
        stripped = stripped.strip()
    data = json.loads(stripped)
    if not isinstance(data, dict):
        raise ValueError("provider response was not a JSON object")
    return data


def _require_str(data: dict, key: str) -> None:
    if not isinstance(data.get(key), str) or not data[key].strip():
        raise ValueError(f"missing/invalid {key!r}")


def _require_bool(data: dict, key: str) -> None:
    if not isinstance(data.get(key), bool):
        raise ValueError(f"missing/invalid {key!r}")


def _require_list(data: dict, key: str) -> None:
    if not isinstance(data.get(key), list):
        raise ValueError(f"missing/invalid {key!r}")


_SPEC_STR_FIELDS = (
    "title",
    "problem_statement",
    "technical_approach",
    "data_migration_impact",
    "security_considerations",
    "observability_requirements",
    "test_plan",
)
_SPEC_LIST_FIELDS = (
    "goals",
    "non_goals",
    "requirements",
    "acceptance_criteria",
    "architecture_components",
    "risks",
    "dependencies",
    "assumptions",
    "unresolved_questions",
    "implementation_stages",
)


def _validate_specification(spec: Any) -> None:
    if not isinstance(spec, dict):
        raise ValueError("'specification' must be an object")
    for key in _SPEC_STR_FIELDS:
        _require_str(spec, key)
    for key in _SPEC_LIST_FIELDS:
        _require_list(spec, key)


def _validate_recall_request_optional(data: dict) -> None:
    """Sprint 18 §4.8/§7: `recall_request` is optional on every PM turn
    kind. Absence and explicit `null` are both "no recall" (§7) -- only
    reject a structurally wrong value (e.g. a string/list/bool) here, since
    a malformed *sub-field* (bad `tags` type, oversized `limit`, ...) is
    `RecallRequest`'s own job to coerce away leniently (schemas.py), never
    a reason to fail the whole planning turn."""
    if "recall_request" not in data:
        return
    value = data["recall_request"]
    if value is not None and not isinstance(value, dict):
        raise ValueError("'recall_request' must be an object or null")


def _reject_recall_request(data: dict) -> None:
    """Sprint 18 §7: only PM turn kinds may emit `recall_request` -- the
    CTO's contract is never extended (§4.8), so a CTO response carrying a
    non-null value here is malformed output and takes the existing
    bounded-retry-then-fail path, the same as any other schema violation."""
    if data.get("recall_request") is not None:
        raise ValueError("'recall_request' is not permitted on CTO turns")


def _validate_pm_analysis(data: dict) -> None:
    _require_bool(data, "needs_clarification")
    _require_str(data, "analysis_summary")
    if data["needs_clarification"] and not [q for q in data.get("questions") or [] if str(q).strip()]:
        raise ValueError("needs_clarification=true requires at least one question")
    _validate_recall_request_optional(data)


def _validate_cto_review(data: dict) -> None:
    _require_bool(data, "blocking")
    _require_str(data, "architecture_notes")
    _require_list(data, "risks")
    if data["blocking"]:
        _require_str(data, "blocking_reason")
    _reject_recall_request(data)


def _validate_pm_draft_or_followup(data: dict) -> None:
    _require_bool(data, "ready_to_draft")
    if data["ready_to_draft"]:
        _validate_specification(data.get("specification"))
    else:
        _require_str(data, "follow_up_question")
    _validate_recall_request_optional(data)


def _validate_cto_followup_answer(data: dict) -> None:
    _require_str(data, "answer")
    _reject_recall_request(data)


def _validate_pm_draft(data: dict) -> None:
    _validate_specification(data.get("specification"))
    _validate_recall_request_optional(data)


_VALIDATORS: dict[str, Callable[[dict], None]] = {
    "pm_analysis": _validate_pm_analysis,
    "cto_review": _validate_cto_review,
    "pm_draft_or_followup": _validate_pm_draft_or_followup,
    "cto_followup_answer": _validate_cto_followup_answer,
    "pm_draft": _validate_pm_draft,
    "pm_revision_draft": _validate_pm_draft,
}

_SPEC_SCHEMA_HINT = (
    '{"title": string, "problem_statement": string, "goals": [string], '
    '"non_goals": [string], "requirements": [string], "acceptance_criteria": [string], '
    '"technical_approach": string, "architecture_components": [string], '
    '"data_migration_impact": string, "security_considerations": string, '
    '"observability_requirements": string, "test_plan": string, '
    '"risks": [{"risk": string, "mitigation": string}], "dependencies": [string], '
    '"assumptions": [string], "unresolved_questions": [string], "implementation_stages": [string]}'
)


def _pm_analysis_message(opts: dict) -> str:
    return (
        f"CEO's request: {opts['request_text']}\n\n"
        "Analyze this request as the PM. Respond with exactly this JSON shape: "
        '{"needs_clarification": bool, "questions": [string, ...], "analysis_summary": string}. '
        "Only set needs_clarification=true, with concrete questions, if scope, security, "
        "cost, or acceptance criteria are materially unclear."
    )


def _cto_review_message(opts: dict) -> str:
    return (
        f"CEO's request: {opts['request_text']}\n\n"
        "Give a technical feasibility review as the CTO. Respond with exactly this JSON "
        'shape: {"blocking": bool, "blocking_reason": string|null, "risks": [string, ...], '
        '"architecture_notes": string}. Only set blocking=true if the request is not '
        "technically feasible as stated."
    )


def _pm_draft_or_followup_message(opts: dict) -> str:
    return (
        f"CEO's request: {opts['request_text']}\n\n"
        "Decide whether you are ready to draft the Project Specification, or need one "
        "bounded follow-up question answered by the CTO first. Respond with exactly this "
        'JSON shape: {"ready_to_draft": bool, "follow_up_question": string|null, '
        f'"specification": {_SPEC_SCHEMA_HINT} or null}}.'
    )


def _cto_followup_answer_message(opts: dict) -> str:
    return (
        f"The PM asked this follow-up question: {opts.get('follow_up_question', '')}\n\n"
        'Answer it as the CTO. Respond with exactly this JSON shape: {"answer": string}.'
    )


def _pm_draft_message(opts: dict) -> str:
    return (
        f"CEO's request: {opts['request_text']}\n\n"
        f"CTO's answer to your follow-up question: {opts.get('follow_up_answer', '')}\n\n"
        "Draft the final Project Specification now. Respond with exactly this JSON shape: "
        f'{{"specification": {_SPEC_SCHEMA_HINT}}}.'
    )


def _pm_revision_draft_message(opts: dict) -> str:
    return (
        f"CEO's request: {opts['request_text']}\n\n"
        f"CEO's revision feedback: {opts.get('revision_feedback', '')}\n\n"
        "Revise the Project Specification to address this feedback. Respond with exactly "
        f'this JSON shape: {{"specification": {_SPEC_SCHEMA_HINT}}}.'
    )


_USER_MESSAGE_BUILDERS: dict[str, Callable[[dict], str]] = {
    "pm_analysis": _pm_analysis_message,
    "cto_review": _cto_review_message,
    "pm_draft_or_followup": _pm_draft_or_followup_message,
    "cto_followup_answer": _cto_followup_answer_message,
    "pm_draft": _pm_draft_message,
    "pm_revision_draft": _pm_revision_draft_message,
}


def _format_recall_message(results: list[RecalledMemory]) -> str:
    """Sprint 18 §7 item 3 -- a small, server-formatted JSON block, never
    raw record content beyond each result's own bounded `preview`. Injected
    as one extra user-role message ahead of the PM's next turn."""
    items = [
        {
            "id": r.id,
            "category": r.category,
            "title": r.title,
            "tags": r.tags,
            "created_at": r.created_at.isoformat(),
            "preview": r.preview,
        }
        for r in results
    ]
    return "Memory recall results (deterministic, keyword+tag+recency match):\n" + json.dumps(
        {"results": items}, indent=2
    )


def _turn_text_for(kind: str, data: dict) -> str:
    if kind == "pm_analysis":
        if data["needs_clarification"]:
            questions = "\n".join(f"- {q}" for q in data["questions"])
            return f"{data['analysis_summary']}\n\nQuestions for the CEO:\n{questions}"
        return data["analysis_summary"]
    if kind == "cto_review":
        if data["blocking"]:
            return f"Blocking feasibility issue: {data['blocking_reason']}"
        return data["architecture_notes"]
    if kind == "pm_draft_or_followup":
        if data["ready_to_draft"]:
            return f"Drafted Project Specification: {data['specification']['title']}"
        return f"Follow-up question for the CTO: {data['follow_up_question']}"
    if kind == "cto_followup_answer":
        return data["answer"]
    # pm_draft, pm_revision_draft
    return f"Drafted Project Specification: {data['specification']['title']}"


def _orm_kind_for(kind: str, data: dict) -> str:
    if kind == "pm_analysis":
        return "analysis"
    if kind == "cto_review":
        return "review"
    if kind == "pm_draft_or_followup":
        return "draft" if data["ready_to_draft"] else "clarification_request"
    if kind == "cto_followup_answer":
        return "clarification_answer"
    if kind == "pm_revision_draft":
        return "revision"
    return "draft"  # pm_draft


class PlanningOrchestrator:
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

    async def start(
        self, project_id: str, request_text: str, source_task_id: str | None = None
    ) -> SpecificationORM:
        agents_by_role, gateway = await self._prepare_run_context(project_id)
        pm_agent = agents_by_role[TEMPLATE.planning_pm_role_key]
        cto_agent = agents_by_role[TEMPLATE.planning_cto_role_key]

        async with self._session_factory() as session:
            spec = SpecificationORM(
                project_id=project_id,
                status=SpecificationStatus.DRAFT.value,
                request_text=request_text,
                source_task_id=source_task_id,
                pm_agent_id=pm_agent.id,
                cto_agent_id=cto_agent.id,
            )
            session.add(spec)
            await session.flush()
            transition(SpecificationStatus.DRAFT, SpecificationStatus.PLANNING, SPECIFICATION_TRANSITIONS)
            spec.status = SpecificationStatus.PLANNING.value
            session.add(ActiveSpecificationLockORM(project_id=project_id, specification_id=spec.id))
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                raise ActivePlanningExistsError(project_id) from None
            spec_id = spec.id

        await self._event_bus.publish(
            build_event(
                type=EventType.SPECIFICATION_REQUESTED,
                project_id=project_id,
                actor=CEO_ACTOR,
                payload={"specification_id": spec_id, "pm_agent_id": pm_agent.id, "cto_agent_id": cto_agent.id},
                reason="CEO submitted a project request for planning",
            )
        )

        await self._run(spec_id, project_id, agents_by_role, gateway, start_kind="pm_analysis", resumed=False)
        return await self._get(spec_id)

    async def resume_after_clarification(self, specification_id: str, answers: list[str]) -> SpecificationORM:
        async with self._session_factory() as session:
            spec = await session.get(SpecificationORM, specification_id)
            if spec is None:
                raise ValueError(f"no such specification {specification_id!r}")
            current = SpecificationStatus(spec.status)
            transition(current, SpecificationStatus.PLANNING, SPECIFICATION_TRANSITIONS)
            resume_stage = spec.resume_stage
            spec.status = SpecificationStatus.PLANNING.value
            spec.resume_stage = None
            spec.updated_at = _now()
            await session.commit()
            project_id = spec.project_id

        await self._persist_ceo_answer_turn(specification_id, project_id, answers)

        agents_by_role, gateway = await self._prepare_run_context(project_id)
        await self._run(
            specification_id, project_id, agents_by_role, gateway, start_kind=resume_stage, resumed=True
        )
        return await self._get(specification_id)

    async def submit_revision(self, specification_id: str, feedback: str) -> SpecificationORM:
        async with self._session_factory() as session:
            spec = await session.get(SpecificationORM, specification_id)
            if spec is None:
                raise ValueError(f"no such specification {specification_id!r}")
            current = SpecificationStatus(spec.status)
            transition(current, SpecificationStatus.REVISION_REQUESTED, SPECIFICATION_TRANSITIONS)
            spec.status = SpecificationStatus.REVISION_REQUESTED.value
            spec.decision_comment = feedback
            spec.updated_at = _now()
            await session.commit()
            project_id, prior_version = spec.project_id, spec.current_version

        await self._event_bus.publish(
            build_event(
                type=EventType.SPECIFICATION_REVISION_REQUESTED,
                project_id=project_id,
                actor=CEO_ACTOR,
                payload={"specification_id": specification_id, "version": prior_version},
                reason=feedback,
            )
        )

        async with self._session_factory() as session:
            spec = await session.get(SpecificationORM, specification_id)
            transition(SpecificationStatus.REVISION_REQUESTED, SpecificationStatus.PLANNING, SPECIFICATION_TRANSITIONS)
            spec.status = SpecificationStatus.PLANNING.value
            spec.updated_at = _now()
            await session.commit()

        agents_by_role, gateway = await self._prepare_run_context(project_id)
        await self._run(
            specification_id,
            project_id,
            agents_by_role,
            gateway,
            start_kind="pm_revision_draft",
            resumed=False,
            revision_feedback=feedback,
        )
        return await self._get(specification_id)

    async def cancel(self, specification_id: str, reason: str | None) -> bool:
        async with self._session_factory() as session:
            spec = await session.get(SpecificationORM, specification_id)
            if spec is None:
                return False
            current = SpecificationStatus(spec.status)
            if SpecificationStatus.CANCELLED not in SPECIFICATION_TRANSITIONS.get(current, set()):
                return False
            spec.status = SpecificationStatus.CANCELLED.value
            spec.stop_reason = "ceo_cancelled"
            spec.decision_comment = reason
            spec.decided_at = _now()
            spec.updated_at = _now()
            await session.commit()
            project_id = spec.project_id
            pm_agent_id, cto_agent_id = spec.pm_agent_id, spec.cto_agent_id

        await self._release_lock(project_id)
        for agent_id in (pm_agent_id, cto_agent_id):
            if agent_id:
                await self._release_agent_to_idle(agent_id, "Planning cancelled by CEO")
        await self._event_bus.publish(
            build_event(
                type=EventType.SPECIFICATION_CANCELLED,
                project_id=project_id,
                actor=CEO_ACTOR,
                payload={"specification_id": specification_id},
                reason=reason or "CEO cancelled planning",
            )
        )
        return True

    # --- context setup ----------------------------------------------------

    async def _get(self, specification_id: str) -> SpecificationORM:
        async with self._session_factory() as session:
            spec = await session.get(SpecificationORM, specification_id)
            if spec is None:
                raise ValueError(f"no such specification {specification_id!r}")
            return spec

    async def _prepare_run_context(self, project_id: str) -> tuple[dict[str, AgentORM], ProviderGateway]:
        async with self._session_factory() as session:
            result = await session.execute(select(AgentORM).where(AgentORM.project_id == project_id))
            rows = list(result.scalars().all())
            project = await session.get(ProjectORM, project_id)

        by_role: dict[str, list[AgentORM]] = {}
        for row in rows:
            by_role.setdefault(row.role_key, []).append(row)

        cto_candidates = by_role.get(TEMPLATE.planning_cto_role_key, [])
        if not cto_candidates:
            raise CTOVacantError(project_id)
        pm_candidates = by_role.get(TEMPLATE.planning_pm_role_key, [])

        pm_agent = await self._resolve_agent(project_id, pm_candidates, TEMPLATE.planning_pm_role_key)
        cto_agent = await self._resolve_agent(project_id, cto_candidates, TEMPLATE.planning_cto_role_key)

        provider_name = project.provider if project else RECOMMENDED_PROVIDER
        gateway = build_gateway(
            provider_name,
            self._secrets,
            event_bus=self._event_bus,
            project_id=project_id,
            session_factory=self._session_factory,
        )
        agents_by_role = {
            TEMPLATE.planning_pm_role_key: pm_agent,
            TEMPLATE.planning_cto_role_key: cto_agent,
        }
        return agents_by_role, gateway

    async def _resolve_agent(self, project_id: str, candidates: list[AgentORM], role_key: str) -> AgentORM:
        """Same selection + observability shape as
        `workflow_engine.engine._resolve_agent` (Sprint 10 §12), duplicated
        rather than imported because that method is a private detail of the
        mission pipeline -- only the shared policy function itself
        (`resolve_employee_for_role`) is re-exported for reuse (Rule #1)."""
        selected, rule = resolve_employee_for_role(candidates)

        now = _now()
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
                reason=f"Resolved {role_key} for planning to {selected.name} ({rule_reason})",
            )
        )
        return selected

    async def _release_agent_to_idle(self, agent_id: str, reason: str) -> None:
        current = await self._agent_runtime.get_state(agent_id)
        if current != AgentState.IDLE:
            if current == AgentState.WAITING_REVIEW:
                await self._agent_runtime.transition(agent_id, AgentState.COMPLETED, reason)
            elif current not in (AgentState.COMPLETED, AgentState.FAILED):
                await self._agent_runtime.transition(agent_id, AgentState.FAILED, reason)
            current = await self._agent_runtime.get_state(agent_id)
            if current != AgentState.IDLE:
                await self._agent_runtime.transition(agent_id, AgentState.IDLE, reason)

    async def _release_lock(self, project_id: str) -> None:
        async with self._session_factory() as session:
            lock = await session.get(ActiveSpecificationLockORM, project_id)
            if lock is not None:
                await session.delete(lock)
                await session.commit()

    # --- turn loop ----------------------------------------------------------

    async def _count_employee_turns(self, specification_id: str) -> int:
        async with self._session_factory() as session:
            result = await session.execute(
                select(SpecificationTurnORM).where(
                    SpecificationTurnORM.specification_id == specification_id,
                    SpecificationTurnORM.actor_role == "employee",
                )
            )
            return len(list(result.scalars().all()))

    async def _run(
        self,
        specification_id: str,
        project_id: str,
        agents_by_role: dict[str, AgentORM],
        gateway: ProviderGateway,
        start_kind: str,
        resumed: bool,
        revision_feedback: str = "",
    ) -> None:
        kind = start_kind
        follow_up_question = ""
        follow_up_answer = ""
        first_iteration = True
        # Sprint 18 §7: set by `_maybe_recall` right after a PM turn whose
        # JSON carried a `recall_request`, consumed exactly once by the
        # *next* turn's `_call_turn` call, then cleared -- there is no
        # persisted cross-turn message list in this orchestrator (each turn
        # is a fresh one-shot `gateway.complete` call), so this local is the
        # entire lifetime of "the next user message".
        pending_recall_message: str | None = None

        while True:
            if await self._count_employee_turns(specification_id) >= MAX_PLANNING_TURNS:
                await self._fail(
                    specification_id,
                    project_id,
                    agents_by_role,
                    "turn_limit_exceeded",
                    PlanningTurnBudgetExhaustedError(specification_id, MAX_PLANNING_TURNS),
                )
                return

            role_key = _role_for_kind(kind)
            agent = agents_by_role[role_key]
            model_ref = TEMPLATE.roles_by_key[role_key].model_ref

            spec = await self._get(specification_id)
            opts: dict[str, Any] = {"request_text": spec.request_text}
            if kind in ("pm_analysis", "cto_review"):
                opts["already_resumed"] = resumed and first_iteration
            if kind == "cto_followup_answer":
                opts["follow_up_question"] = follow_up_question
            if kind == "pm_draft":
                opts["follow_up_answer"] = follow_up_answer
            if kind == "pm_revision_draft":
                opts["revision_feedback"] = revision_feedback

            turn_recall_message, pending_recall_message = pending_recall_message, None
            try:
                data = await self._run_turn(
                    agent, role_key, kind, model_ref, opts, gateway, recall_message=turn_recall_message
                )
            except MalformedProviderOutputError as exc:
                await self._fail(specification_id, project_id, agents_by_role, "malformed_provider_output", exc)
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - any other provider/runtime failure ends planning
                logger.exception("planning turn %s failed for specification %s", kind, specification_id)
                await self._fail(specification_id, project_id, agents_by_role, "provider_error", exc)
                return

            await self._persist_turn(specification_id, project_id, agent, role_key, kind, data)
            first_iteration = False

            if role_key == TEMPLATE.planning_pm_role_key:
                pending_recall_message = await self._maybe_recall(specification_id, project_id, agent, data)

            if kind == "pm_analysis":
                if data["needs_clarification"]:
                    await self._enter_clarification(specification_id, project_id, data["questions"], "pm_analysis")
                    return
                kind = "cto_review"
                continue

            if kind == "cto_review":
                if data["blocking"]:
                    await self._enter_clarification(
                        specification_id, project_id, [data["blocking_reason"]], "cto_review"
                    )
                    return
                kind = "pm_draft_or_followup"
                continue

            if kind == "pm_draft_or_followup":
                if data["ready_to_draft"]:
                    await self._publish_ready(specification_id, project_id, data["specification"])
                    return
                follow_up_question = data["follow_up_question"]
                kind = "cto_followup_answer"
                continue

            if kind == "cto_followup_answer":
                follow_up_answer = data["answer"]
                kind = "pm_draft"
                continue

            # pm_draft, pm_revision_draft: both terminal drafts
            await self._publish_ready(specification_id, project_id, data["specification"])
            return

    async def _run_turn(
        self,
        agent: AgentORM,
        role_key: str,
        kind: str,
        model_ref: str,
        opts: dict[str, Any],
        gateway: ProviderGateway,
        recall_message: str | None = None,
    ) -> dict:
        """Cycle the resolved Employee through Assigned->Planning->Working->
        WaitingReview->Completed->Idle around one structured-output call,
        mirroring `workflow_engine.engine._run_role` so a planning turn
        never strands PM/CTO busy on cancel or failure (brief §5.6)."""
        try:
            await self._agent_runtime.transition(agent.id, AgentState.ASSIGNED, f"Picked up planning turn '{kind}'")
            await self._agent_runtime.transition(agent.id, AgentState.PLANNING, "Reviewing planning context")
            await self._agent_runtime.transition(agent.id, AgentState.WORKING, "Producing structured planning output")

            data = await self._call_turn(gateway, model_ref, agent, role_key, kind, opts, recall_message=recall_message)

            await self._agent_runtime.transition(agent.id, AgentState.WAITING_REVIEW, "Planning output ready")
            await self._agent_runtime.transition(agent.id, AgentState.COMPLETED, "Turn handed off")
            await self._agent_runtime.transition(agent.id, AgentState.IDLE, "Back to the bench")
            return data
        except asyncio.CancelledError:
            await self._release_agent_to_idle(agent.id, "Planning cancelled")
            raise
        except Exception:
            await self._release_agent_to_idle(agent.id, "Planning turn failed")
            raise

    async def _call_turn(
        self,
        gateway: ProviderGateway,
        model_ref: str,
        agent: AgentORM,
        role_key: str,
        kind: str,
        opts: dict[str, Any],
        recall_message: str | None = None,
    ) -> dict:
        system = prompt_builder.build(
            AgentProfile.model_validate(agent.profile), role_key, contract_override=TEMPLATE.planning_contracts[role_key]
        )
        user_content = _USER_MESSAGE_BUILDERS[kind](opts)
        validator = _VALIDATORS[kind]

        # Sprint 18 §7 item 4: the recall result message (if any) is
        # prepended as its own user-role message ahead of this turn's usual
        # one, rather than concatenated into `user_content` -- keeps the
        # server-owned recall block visually/structurally distinct from the
        # turn-kind-specific prompt built by `_USER_MESSAGE_BUILDERS`.
        messages: list[dict[str, str]] = []
        if recall_message is not None:
            messages.append({"role": "user", "content": recall_message})
        messages.append({"role": "user", "content": user_content})

        for attempt in range(1, MAX_MALFORMED_ATTEMPTS + 1):
            result = await gateway.complete(
                model_ref,
                system,
                messages,
                agent_override=_agent_model_override(agent),
                planning_turn_kind=kind,
                **opts,
            )
            try:
                data = _parse_json(result.text)
                validator(data)
                return data
            except (ValueError, KeyError, TypeError) as exc:
                logger.warning(
                    "malformed planning output for %s (attempt %s/%s): %s",
                    kind,
                    attempt,
                    MAX_MALFORMED_ATTEMPTS,
                    exc,
                )
        raise MalformedProviderOutputError(kind, MAX_MALFORMED_ATTEMPTS)

    # --- persistence + events ------------------------------------------------

    async def _persist_turn(
        self, specification_id: str, project_id: str, agent: AgentORM, role_key: str, kind: str, data: dict
    ) -> None:
        orm_kind = _orm_kind_for(kind, data)
        text = _turn_text_for(kind, data)
        async with self._session_factory() as session:
            spec = await session.get(SpecificationORM, specification_id)
            turn_index = spec.turn_count
            session.add(
                SpecificationTurnORM(
                    specification_id=specification_id,
                    turn_index=turn_index,
                    actor_role="employee",
                    role_key=role_key,
                    agent_id=agent.id,
                    kind=orm_kind,
                    text=text,
                )
            )
            spec.turn_count = turn_index + 1
            spec.updated_at = _now()
            await session.commit()

        await self._event_bus.publish(
            build_event(
                type=EventType.SPECIFICATION_TURN_POSTED,
                project_id=project_id,
                actor=Actor(role="employee", id=agent.id, name=agent.name),
                payload={
                    "specification_id": specification_id,
                    "turn_index": turn_index,
                    "role_key": role_key,
                    "agent_id": agent.id,
                    "kind": orm_kind,
                },
                reason=text[:200],
            )
        )

    async def _maybe_recall(
        self, specification_id: str, project_id: str, agent: AgentORM, data: dict
    ) -> str | None:
        """Sprint 18 §7: fires only when the just-persisted PM turn's JSON
        carried a non-null `recall_request` (`_reject_recall_request`
        already keeps this off every CTO turn kind, so `data` is always a
        PM turn's output when this is called). Deterministic, zero-LLM:
        `memory.recall` is a plain read against `memory_records`. Always
        publishes `MEMORY_RECALLED` -- even on zero matches, so a PM asking
        recall and getting nothing is still observable on the Timeline --
        but only returns a message for the next turn when there is
        something worth injecting (§7 item 6)."""
        raw = data.get("recall_request")
        if raw is None:
            return None
        request = RecallRequest.model_validate(raw) if isinstance(raw, dict) else RecallRequest()
        results = await memory_recall(self._session_factory, project_id, request)
        requested_categories = (
            list(request.categories) if request.categories is not None else list(MEMORY_CATEGORIES)
        )

        await self._event_bus.publish(
            build_event(
                type=EventType.MEMORY_RECALLED,
                project_id=project_id,
                actor=Actor(role="employee", id=agent.id, name=agent.name),
                payload={
                    "spec_id": specification_id,
                    "requested_categories": requested_categories,
                    "match_count": len(results),
                    "memory_ids": [r.id for r in results],
                },
                reason=f"PM recalled {len(results)} memory record(s)",
            )
        )
        if not results:
            return None
        return _format_recall_message(results)

    async def _persist_ceo_answer_turn(self, specification_id: str, project_id: str, answers: list[str]) -> None:
        text = "\n".join(f"- {a}" for a in answers)
        async with self._session_factory() as session:
            spec = await session.get(SpecificationORM, specification_id)
            turn_index = spec.turn_count
            session.add(
                SpecificationTurnORM(
                    specification_id=specification_id,
                    turn_index=turn_index,
                    actor_role="ceo",
                    role_key=None,
                    agent_id=None,
                    kind="clarification_answer",
                    text=text,
                )
            )
            spec.turn_count = turn_index + 1
            spec.clarification_answers = [*(spec.clarification_answers or []), *answers]
            spec.updated_at = _now()
            await session.commit()

        await self._event_bus.publish(
            build_event(
                type=EventType.SPECIFICATION_CLARIFICATION_ANSWERED,
                project_id=project_id,
                actor=CEO_ACTOR,
                payload={"specification_id": specification_id},
                reason="CEO answered the PM's clarification questions",
            )
        )

    async def _enter_clarification(
        self, specification_id: str, project_id: str, questions: list[str], resume_stage: str
    ) -> None:
        async with self._session_factory() as session:
            spec = await session.get(SpecificationORM, specification_id)
            current = SpecificationStatus(spec.status)
            transition(current, SpecificationStatus.CLARIFICATION_REQUIRED, SPECIFICATION_TRANSITIONS)
            spec.status = SpecificationStatus.CLARIFICATION_REQUIRED.value
            spec.clarification_questions = questions
            spec.resume_stage = resume_stage
            spec.stop_reason = "clarification_required"
            spec.updated_at = _now()
            await session.commit()

        await self._event_bus.publish(
            build_event(
                type=EventType.SPECIFICATION_CLARIFICATION_REQUESTED,
                project_id=project_id,
                actor=SYSTEM_ACTOR,
                payload={"specification_id": specification_id, "questions": questions},
                reason="Planning needs CEO clarification before it can continue",
            )
        )

    async def _publish_ready(self, specification_id: str, project_id: str, spec_data: dict) -> None:
        async with self._session_factory() as session:
            spec = await session.get(SpecificationORM, specification_id)
            current = SpecificationStatus(spec.status)
            transition(current, SpecificationStatus.READY_FOR_REVIEW, SPECIFICATION_TRANSITIONS)
            new_version = spec.current_version + 1
            session.add(
                SpecificationVersionORM(
                    specification_id=specification_id,
                    version=new_version,
                    **{k: spec_data[k] for k in (*_SPEC_STR_FIELDS, *_SPEC_LIST_FIELDS)},
                )
            )
            spec.current_version = new_version
            spec.status = SpecificationStatus.READY_FOR_REVIEW.value
            spec.resume_stage = None
            spec.stop_reason = "ready_for_review"
            spec.updated_at = _now()
            await session.commit()

        await self._event_bus.publish(
            build_event(
                type=EventType.SPECIFICATION_READY,
                project_id=project_id,
                actor=SYSTEM_ACTOR,
                payload={"specification_id": specification_id, "version": new_version},
                reason=f"Project Specification v{new_version} ready for CEO review",
            )
        )

    async def _fail(
        self,
        specification_id: str,
        project_id: str,
        agents_by_role: dict[str, AgentORM],
        stop_reason: str,
        exc: Exception,
    ) -> None:
        async with self._session_factory() as session:
            spec = await session.get(SpecificationORM, specification_id)
            current = SpecificationStatus(spec.status)
            if SpecificationStatus.FAILED in SPECIFICATION_TRANSITIONS.get(current, set()):
                spec.status = SpecificationStatus.FAILED.value
            spec.stop_reason = stop_reason
            spec.updated_at = _now()
            await session.commit()

        await self._release_lock(project_id)
        for agent in agents_by_role.values():
            await self._release_agent_to_idle(agent.id, "Planning failed")

        await self._event_bus.publish(
            build_event(
                type=EventType.SPECIFICATION_FAILED,
                project_id=project_id,
                actor=SYSTEM_ACTOR,
                payload={"specification_id": specification_id, "reason": str(exc)},
                reason=f"Planning failed: {stop_reason}",
            )
        )
