"""Sprint 13 §4.3/§4.4/§6: the deterministic CEO next-action policy.

A pure function over a plain-dataclass `WorkspaceFacts` snapshot -- no ORM
objects, no session, no I/O -- so it is unit-testable without a database
(docs/prompts/sprint-13.md §6 "keep next-action policy separately
testable"). `service.py` is the only caller; it is responsible for
translating ORM rows into `WorkspaceFacts` and translating this module's
`NextAction`/`Focus` back into the response.

Precedence (docs/prompts/sprint-13.md §4.4), verified against the actual
shipped state machines and implemented in this exact order:

1. CEO clarification required
2. Specification ready for review
3. Revision feedback or retry required -- reserved, currently unreachable
   (docs/DECISIONS.md #218: no shipped lifecycle path produces this today)
4. Mission decision/approval required
5. Planning or mission failure requiring attention
6. Approved specification ready to begin execution
7. Active planning or mission in progress
8. Company setup requirement, including vacant critical leadership
9. Start a new project or mission
10. No action / monitor activity
"""

from __future__ import annotations

from dataclasses import dataclass

from ...core.lifecycle.specification_states import SpecificationStatus
from .schemas import Focus, NextAction

_IN_PROGRESS_SPEC_STATUSES = {
    SpecificationStatus.DRAFT.value,
    SpecificationStatus.PLANNING.value,
    SpecificationStatus.REVISION_REQUESTED.value,
}


@dataclass(frozen=True)
class SpecFacts:
    id: str
    status: str
    current_version: int
    turn_count: int
    clarification_questions: tuple[str, ...]
    has_execution_task: bool


@dataclass(frozen=True)
class ApprovalFacts:
    id: str
    task_id: str
    subject: str


@dataclass(frozen=True)
class TaskFacts:
    id: str
    title: str
    state: str


@dataclass(frozen=True)
class LeadershipFacts:
    role_key: str
    title: str
    occupied: bool


@dataclass(frozen=True)
class WorkspaceFacts:
    project_id: str
    latest_specification: SpecFacts | None
    pending_approval: ApprovalFacts | None
    failed_or_blocked_tasks: tuple[TaskFacts, ...]
    active_tasks: tuple[TaskFacts, ...]
    leadership: tuple[LeadershipFacts, ...]
    has_any_task: bool


def _spec_route(project_id: str, specification_id: str) -> str:
    return f"/company/{project_id}/specifications/{specification_id}"


def _mission_route(project_id: str, task_id: str) -> str:
    return f"/company/{project_id}/missions/{task_id}"


def _decisions_route(project_id: str) -> str:
    return f"/company/{project_id}/decisions"


def _employees_route(project_id: str) -> str:
    return f"/company/{project_id}/employees"


def _missions_route(project_id: str) -> str:
    return f"/company/{project_id}/missions"


def derive(facts: WorkspaceFacts) -> tuple[NextAction, Focus]:
    """Returns (next_action, focus). `focus` always mirrors next_action's
    target when one exists, so a snapshot can never point next_action at a
    resource `focus` doesn't also describe (§4.6 consistency requirement)."""
    spec = facts.latest_specification

    # Tier 1 — CEO clarification required.
    if spec is not None and spec.status == SpecificationStatus.CLARIFICATION_REQUIRED.value:
        count = len(spec.clarification_questions)
        action = NextAction(
            kind="answer_clarification",
            title="Answer the PM/CTO's question",
            explanation=(
                f"Planning is paused on {count} question{'s' if count != 1 else ''} "
                "that need your answer before it can continue."
            ),
            target_resource_type="specification",
            target_resource_id=spec.id,
            route=_spec_route(facts.project_id, spec.id),
            urgency="high",
            requires_ceo_input=True,
        )
        return action, Focus(resource_type="specification", resource_id=spec.id, status=spec.status)

    # Tier 2 — Specification ready for review.
    if spec is not None and spec.status == SpecificationStatus.READY_FOR_REVIEW.value:
        action = NextAction(
            kind="review_specification",
            title="Review the Project Specification",
            explanation=f"Version {spec.current_version} is ready for your approval, revision request, or rejection.",
            target_resource_type="specification",
            target_resource_id=spec.id,
            route=_spec_route(facts.project_id, spec.id),
            urgency="high",
            requires_ceo_input=True,
        )
        return action, Focus(resource_type="specification", resource_id=spec.id, status=spec.status)

    # Tier 3 — revision/retry: no shipped predicate today (DECISIONS.md #218).

    # Tier 4 — Mission decision/approval required.
    if facts.pending_approval is not None:
        approval = facts.pending_approval
        action = NextAction(
            kind="review_approval",
            title="Review a Mission decision",
            explanation=f"{approval.subject} is waiting on your approve/request-changes/reject decision.",
            target_resource_type="task",
            target_resource_id=approval.task_id,
            route=_decisions_route(facts.project_id),
            urgency="high",
            requires_ceo_input=True,
        )
        return action, Focus(resource_type="task", resource_id=approval.task_id, status="pending_approval")

    # Tier 5 — Planning or mission failure requiring attention.
    if spec is not None and spec.status == SpecificationStatus.FAILED.value:
        action = NextAction(
            kind="resolve_planning_failure",
            title="Planning failed",
            explanation="The PM/CTO planning run did not reach a reviewable specification and needs your attention.",
            target_resource_type="specification",
            target_resource_id=spec.id,
            route=_spec_route(facts.project_id, spec.id),
            urgency="high",
            requires_ceo_input=True,
        )
        return action, Focus(resource_type="specification", resource_id=spec.id, status=spec.status)
    if facts.failed_or_blocked_tasks:
        task = facts.failed_or_blocked_tasks[0]
        action = NextAction(
            kind="resolve_mission_failure",
            title="A mission needs attention",
            explanation=f"'{task.title}' is {task.state} and has no automatic next step.",
            target_resource_type="task",
            target_resource_id=task.id,
            route=_mission_route(facts.project_id, task.id),
            urgency="high",
            requires_ceo_input=True,
        )
        return action, Focus(resource_type="task", resource_id=task.id, status=task.state)

    # Tier 6 — Approved specification ready to begin execution.
    if (
        spec is not None
        and spec.status == SpecificationStatus.APPROVED.value
        and not spec.has_execution_task
    ):
        action = NextAction(
            kind="begin_execution",
            title="Start the approved Mission",
            explanation=f"Version {spec.current_version} was approved and is ready to begin execution.",
            target_resource_type="specification",
            target_resource_id=spec.id,
            route=_spec_route(facts.project_id, spec.id),
            urgency="medium",
            requires_ceo_input=True,
        )
        return action, Focus(resource_type="specification", resource_id=spec.id, status=spec.status)

    # Tier 7 — Active planning or mission in progress.
    if spec is not None and spec.status in _IN_PROGRESS_SPEC_STATUSES:
        action = NextAction(
            kind="monitor_planning",
            title="Planning in progress",
            explanation="Your PM and CTO are working on this specification. No input needed yet.",
            target_resource_type="specification",
            target_resource_id=spec.id,
            route=_spec_route(facts.project_id, spec.id),
            urgency="low",
            requires_ceo_input=False,
        )
        return action, Focus(resource_type="specification", resource_id=spec.id, status=spec.status)
    if facts.active_tasks:
        task = facts.active_tasks[0]
        action = NextAction(
            kind="monitor_mission",
            title="A mission is in progress",
            explanation=f"'{task.title}' is {task.state}. No input needed yet.",
            target_resource_type="task",
            target_resource_id=task.id,
            route=_mission_route(facts.project_id, task.id),
            urgency="low",
            requires_ceo_input=False,
        )
        return action, Focus(resource_type="task", resource_id=task.id, status=task.state)

    # Tier 8 — Company setup requirement, including vacant critical leadership.
    vacant = [role for role in facts.leadership if not role.occupied]
    if vacant:
        role = vacant[0]
        action = NextAction(
            kind="setup_leadership",
            title=f"Hire a {role.title}",
            explanation=f"The {role.title} position is vacant.",
            target_resource_type="role",
            target_resource_id=role.role_key,
            route=_employees_route(facts.project_id),
            urgency="medium",
            requires_ceo_input=True,
        )
        return action, Focus(resource_type="role", resource_id=role.role_key, status="vacant")

    # Tier 9 — Start a new project or mission.
    if not facts.has_any_task:
        action = NextAction(
            kind="start_mission",
            title="Start your first mission",
            explanation="This company has no missions yet.",
            target_resource_type=None,
            target_resource_id=None,
            route=_missions_route(facts.project_id),
            urgency="low",
            requires_ceo_input=True,
        )
        return action, Focus(resource_type=None, resource_id=None, status=None)

    # Tier 10 — No action / monitor activity.
    action = NextAction(
        kind="no_action",
        title="Nothing needs your attention",
        explanation="Everything is quiet right now.",
        target_resource_type=None,
        target_resource_id=None,
        route=None,
        urgency="low",
        requires_ceo_input=False,
    )
    return action, Focus(resource_type=None, resource_id=None, status=None)
