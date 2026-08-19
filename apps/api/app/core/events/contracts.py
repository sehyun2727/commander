"""Per-type payload contracts, plus a typed factory for building `Event`s.

Each payload model documents (and validates) the shape of `Event.payload`
for one `EventType`. `PAYLOAD_MODELS` maps type -> model so both the event
factory below and `scripts/generate_ts_schemas.py` have one source of
truth to walk.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from ..lifecycle.agent_states import AgentState
from ..lifecycle.task_states import TaskState
from .base import Actor, Event, EventKind
from .types import EventType


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- Projects (Company) ------------------------------------------------------

class ProjectCreatedPayload(Payload):
    name: str


class ProjectArchivedPayload(Payload):
    pass


# --- Tasks (Missions) ---------------------------------------------------------

class TaskCreatedPayload(Payload):
    task_id: str
    title: str
    priority: str = "normal"


class TaskAssignedPayload(Payload):
    task_id: str
    agent_id: str
    attempt: int = 1


class TaskStartedPayload(Payload):
    task_id: str
    agent_id: str


class TaskCompletedPayload(Payload):
    task_id: str


class TaskFailedPayload(Payload):
    task_id: str
    # Sprint 17 §4.10 (DECISIONS.md #239): optional, additive -- lets the
    # Timeline/dashboard distinguish self-correction exhaustion and
    # employee surrender from every other pipeline failure without a
    # schema change. Every pre-Sprint-17 TASK_FAILED payload validates
    # unchanged (defaults to None).
    reason_code: str | None = None


class TaskRetriedPayload(Payload):
    task_id: str
    attempt: int = 1


class TaskCancelledPayload(Payload):
    task_id: str


class TaskStateChangedPayload(Payload):
    task_id: str
    previous_state: TaskState
    new_state: TaskState


class TaskRecoveredPayload(Payload):
    task_id: str
    previous_state: TaskState


class BudgetExceededPayload(Payload):
    task_id: str
    limit_kind: Literal["tokens", "usd", "seconds"]
    limit_value: float
    observed_value: float
    stage: str


# --- Agents (Employees) -------------------------------------------------------

class AgentCreatedPayload(Payload):
    agent_id: str
    role: str
    name: str


class AgentStartedPayload(Payload):
    agent_id: str
    role: str


class AgentStoppedPayload(Payload):
    agent_id: str


class AgentStateChangedPayload(Payload):
    agent_id: str
    previous_state: AgentState
    new_state: AgentState


class CodingStartedPayload(Payload):
    agent_id: str
    task_id: str


class AgentProfileUpdatedPayload(Payload):
    agent_id: str
    changed_fields: list[str]


class AgentResolvedPayload(Payload):
    role_key: str
    agent_id: str
    rule: Literal["idle", "no_idle_fallback"]


class AgentHiredPayload(Payload):
    agent_id: str
    role_key: str
    model_ref: str | None
    skill_template_key: str


class AgentSelfCorrectionTriggeredPayload(Payload):
    """Sprint 17 §4.11 (DECISIONS.md #239): one coarse Timeline event per
    tool loop, emitted only on the *first* forced fix-and-retry
    interception -- per-attempt/per-rollback detail lives in the durable
    `HarnessToolCallORM` audit table (§4.12), not as additional events."""

    task_id: str
    agent_id: str
    attempts_permitted: int


# --- Workspace (Sprint 5) --------------------------------------------------------

class WorkspaceInitializedPayload(Payload):
    pass


class CodeChangedPayload(Payload):
    branch_name: str
    commit_sha: str
    files_added: int
    files_modified: int
    files_deleted: int
    additions: int
    deletions: int
    summary: str


class BranchMergedPayload(Payload):
    branch_name: str
    commit_sha: str


# --- Models / providers (Company Settings) --------------------------------------

class ModelChangedPayload(Payload):
    role: str  # "planner" | "builder" | "reviewer"
    previous_model: str
    new_model: str


class ProviderChangedPayload(Payload):
    previous_provider: str
    new_provider: str


class ProviderRetriedPayload(Payload):
    provider: str
    attempt: int


# --- Workflow (review / deployment) ---------------------------------------------

class ReviewStartedPayload(Payload):
    task_id: str
    reviewer_agent_id: str


class ReviewCompletedPayload(Payload):
    task_id: str
    outcome: str  # "approved" | "changes_requested"
    # Sprint 18 §4.1 (DECISIONS.md #243): the Reviewer's leniently-parsed
    # Problem/Recommendation/Risk/Impact sections, carried directly on the
    # event so a `reviewer_feedback` Memory extractor never has to query
    # ApprovalORM (which is created and committed *after* this event
    # publishes, in engine.py -- see #243). Additive, defaults empty, every
    # pre-Sprint-18 payload still validates unchanged.
    sections: dict[str, str] = {}


class BugFoundPayload(Payload):
    task_id: str
    description: str


class DeploymentStartedPayload(Payload):
    deployment_id: str


class DeploymentCompletedPayload(Payload):
    deployment_id: str


class DeploymentFailedPayload(Payload):
    deployment_id: str


# --- Execution (Sandbox) — Sprint 6 -----------------------------------------------

class CheckOutcome(BaseModel):
    """One check's result, nested inside `ExecutionCompletedPayload` --
    not itself a top-level event payload, so it isn't in `PAYLOAD_MODELS`
    (but IS in `scripts/generate_ts_schemas.py`'s MODELS list so its TS
    interface still gets emitted)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    status: Literal["passed", "failed", "could_not_run"]
    duration_seconds: float
    output: str


class ExecutionStartedPayload(Payload):
    task_id: str
    check_names: list[str]


class ExecutionCompletedPayload(Payload):
    task_id: str
    results: list[CheckOutcome]
    passed_count: int
    total_count: int


# --- Approvals (CEO Decisions) ---------------------------------------------------

class ApprovalRequestedPayload(Payload):
    approval_id: str
    task_id: str
    subject: str  # e.g. "task_review", "provider_change"


class ApprovalGrantedPayload(Payload):
    approval_id: str


class ApprovalRejectedPayload(Payload):
    approval_id: str


class ApprovalChangesRequestedPayload(Payload):
    approval_id: str


# --- System ----------------------------------------------------------------------

class SystemHeartbeatPayload(Payload):
    pass


# --- Conversation (Meetings) ------------------------------------------------------

class ConversationMessagePayload(Payload):
    text: str
    agent_id: str | None = None
    task_id: str | None = None


class ConversationMessageDeltaPayload(Payload):
    text: str
    agent_id: str | None = None
    task_id: str | None = None
    done: bool = False


# --- Planning (PM <-> CTO) and Project Specification — Sprint 12 -----------------

class SpecificationRequestedPayload(Payload):
    specification_id: str
    pm_agent_id: str
    cto_agent_id: str


class SpecificationTurnPostedPayload(Payload):
    specification_id: str
    turn_index: int
    role_key: str | None
    agent_id: str | None
    kind: str


class SpecificationClarificationRequestedPayload(Payload):
    specification_id: str
    questions: list[str]


class SpecificationClarificationAnsweredPayload(Payload):
    specification_id: str


class SpecificationReadyPayload(Payload):
    specification_id: str
    version: int


class SpecificationApprovedPayload(Payload):
    specification_id: str
    version: int


class SpecificationRevisionRequestedPayload(Payload):
    specification_id: str
    version: int


class SpecificationRejectedPayload(Payload):
    specification_id: str


class SpecificationCancelledPayload(Payload):
    specification_id: str


class SpecificationFailedPayload(Payload):
    specification_id: str
    reason: str


# --- Project Memory — Sprint 18 -----------------------------------------------

class MemoryRecordedPayload(Payload):
    """One deterministic Memory projection wrote a new record. Deliberately
    content-free (no title/content_json/tags/keywords_text) -- the Timeline
    should be able to say a memory was recorded and where it came from
    without becoming a second copy of the record itself (DECISIONS.md #243,
    mirrors AgentSelfCorrectionTriggeredPayload's Sprint 17 shape)."""

    memory_id: str
    category: str
    source_event_id: str
    source_task_id: str | None = None
    source_specification_id: str | None = None


class MemoryRecalledPayload(Payload):
    """The PM explicitly requested recall during PM<->CTO planning. No
    preview text, no keyword echo, no record content -- just enough to
    audit that recall happened, for what, and how many records matched.
    `requested_categories` is always the *resolved* list (all six when the
    PM's request omitted `categories`), never null -- see sprint-18.md
    §4.12."""

    spec_id: str | None = None
    requested_categories: list[str]
    match_count: int
    memory_ids: list[str]


PAYLOAD_MODELS: dict[EventType, type[Payload]] = {
    EventType.PROJECT_CREATED: ProjectCreatedPayload,
    EventType.PROJECT_ARCHIVED: ProjectArchivedPayload,
    EventType.TASK_CREATED: TaskCreatedPayload,
    EventType.TASK_ASSIGNED: TaskAssignedPayload,
    EventType.TASK_STARTED: TaskStartedPayload,
    EventType.TASK_COMPLETED: TaskCompletedPayload,
    EventType.TASK_FAILED: TaskFailedPayload,
    EventType.TASK_RETRIED: TaskRetriedPayload,
    EventType.TASK_CANCELLED: TaskCancelledPayload,
    EventType.TASK_STATE_CHANGED: TaskStateChangedPayload,
    EventType.TASK_RECOVERED: TaskRecoveredPayload,
    EventType.BUDGET_EXCEEDED: BudgetExceededPayload,
    EventType.AGENT_CREATED: AgentCreatedPayload,
    EventType.AGENT_STARTED: AgentStartedPayload,
    EventType.AGENT_STOPPED: AgentStoppedPayload,
    EventType.AGENT_STATE_CHANGED: AgentStateChangedPayload,
    EventType.AGENT_PROFILE_UPDATED: AgentProfileUpdatedPayload,
    EventType.CODING_STARTED: CodingStartedPayload,
    EventType.AGENT_RESOLVED: AgentResolvedPayload,
    EventType.AGENT_HIRED: AgentHiredPayload,
    EventType.SELF_CORRECTION_TRIGGERED: AgentSelfCorrectionTriggeredPayload,
    EventType.WORKSPACE_INITIALIZED: WorkspaceInitializedPayload,
    EventType.CODE_CHANGED: CodeChangedPayload,
    EventType.BRANCH_MERGED: BranchMergedPayload,
    EventType.MODEL_CHANGED: ModelChangedPayload,
    EventType.PROVIDER_CHANGED: ProviderChangedPayload,
    EventType.PROVIDER_RETRIED: ProviderRetriedPayload,
    EventType.REVIEW_STARTED: ReviewStartedPayload,
    EventType.REVIEW_COMPLETED: ReviewCompletedPayload,
    EventType.BUG_FOUND: BugFoundPayload,
    EventType.DEPLOYMENT_STARTED: DeploymentStartedPayload,
    EventType.DEPLOYMENT_COMPLETED: DeploymentCompletedPayload,
    EventType.DEPLOYMENT_FAILED: DeploymentFailedPayload,
    EventType.EXECUTION_STARTED: ExecutionStartedPayload,
    EventType.EXECUTION_COMPLETED: ExecutionCompletedPayload,
    EventType.APPROVAL_REQUESTED: ApprovalRequestedPayload,
    EventType.APPROVAL_GRANTED: ApprovalGrantedPayload,
    EventType.APPROVAL_REJECTED: ApprovalRejectedPayload,
    EventType.APPROVAL_CHANGES_REQUESTED: ApprovalChangesRequestedPayload,
    EventType.SYSTEM_HEARTBEAT: SystemHeartbeatPayload,
    EventType.CONVERSATION_MESSAGE: ConversationMessagePayload,
    EventType.CONVERSATION_MESSAGE_DELTA: ConversationMessageDeltaPayload,
    EventType.SPECIFICATION_REQUESTED: SpecificationRequestedPayload,
    EventType.SPECIFICATION_TURN_POSTED: SpecificationTurnPostedPayload,
    EventType.SPECIFICATION_CLARIFICATION_REQUESTED: SpecificationClarificationRequestedPayload,
    EventType.SPECIFICATION_CLARIFICATION_ANSWERED: SpecificationClarificationAnsweredPayload,
    EventType.SPECIFICATION_READY: SpecificationReadyPayload,
    EventType.SPECIFICATION_APPROVED: SpecificationApprovedPayload,
    EventType.SPECIFICATION_REVISION_REQUESTED: SpecificationRevisionRequestedPayload,
    EventType.SPECIFICATION_REJECTED: SpecificationRejectedPayload,
    EventType.SPECIFICATION_CANCELLED: SpecificationCancelledPayload,
    EventType.SPECIFICATION_FAILED: SpecificationFailedPayload,
    EventType.MEMORY_RECORDED: MemoryRecordedPayload,
    EventType.MEMORY_RECALLED: MemoryRecalledPayload,
}

_CONVERSATION_TYPES = {EventType.CONVERSATION_MESSAGE, EventType.CONVERSATION_MESSAGE_DELTA}


def build_event(
    *,
    type: EventType,
    project_id: str,
    actor: Actor,
    payload: Payload | dict,
    reason: str | None = None,
    kind: EventKind | None = None,
) -> Event:
    """Validate `payload` against the model registered for `type`, then
    build the unified `Event` envelope that gets persisted/published."""
    model = PAYLOAD_MODELS[type]
    validated = payload if isinstance(payload, model) else model.model_validate(payload)
    resolved_kind: EventKind = kind or ("conversation" if type in _CONVERSATION_TYPES else "system")
    return Event(
        project_id=project_id,
        kind=resolved_kind,
        type=type,
        actor=actor,
        payload=validated.model_dump(mode="json"),
        reason=reason,
    )
