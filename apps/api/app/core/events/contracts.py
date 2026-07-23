"""Per-type payload contracts, plus a typed factory for building `Event`s.

Each payload model documents (and validates) the shape of `Event.payload`
for one `EventType`. `PAYLOAD_MODELS` maps type -> model so both the event
factory below and `scripts/generate_ts_schemas.py` have one source of
truth to walk.
"""

from __future__ import annotations

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


class TaskRetriedPayload(Payload):
    task_id: str
    attempt: int = 1


class TaskCancelledPayload(Payload):
    task_id: str


class TaskStateChangedPayload(Payload):
    task_id: str
    previous_state: TaskState
    new_state: TaskState


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


# --- Workspace -----------------------------------------------------------------

class WorkspaceFileChangedPayload(Payload):
    path: str
    change_kind: str  # "added" | "modified" | "deleted"


class WorkspaceCommittedPayload(Payload):
    commit_sha: str
    summary: str


class WorkspaceBranchCreatedPayload(Payload):
    branch_name: str


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


class BugFoundPayload(Payload):
    task_id: str
    description: str


class DeploymentStartedPayload(Payload):
    deployment_id: str


class DeploymentCompletedPayload(Payload):
    deployment_id: str


class DeploymentFailedPayload(Payload):
    deployment_id: str


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
    EventType.AGENT_CREATED: AgentCreatedPayload,
    EventType.AGENT_STARTED: AgentStartedPayload,
    EventType.AGENT_STOPPED: AgentStoppedPayload,
    EventType.AGENT_STATE_CHANGED: AgentStateChangedPayload,
    EventType.CODING_STARTED: CodingStartedPayload,
    EventType.WORKSPACE_FILE_CHANGED: WorkspaceFileChangedPayload,
    EventType.WORKSPACE_COMMITTED: WorkspaceCommittedPayload,
    EventType.WORKSPACE_BRANCH_CREATED: WorkspaceBranchCreatedPayload,
    EventType.MODEL_CHANGED: ModelChangedPayload,
    EventType.PROVIDER_CHANGED: ProviderChangedPayload,
    EventType.PROVIDER_RETRIED: ProviderRetriedPayload,
    EventType.REVIEW_STARTED: ReviewStartedPayload,
    EventType.REVIEW_COMPLETED: ReviewCompletedPayload,
    EventType.BUG_FOUND: BugFoundPayload,
    EventType.DEPLOYMENT_STARTED: DeploymentStartedPayload,
    EventType.DEPLOYMENT_COMPLETED: DeploymentCompletedPayload,
    EventType.DEPLOYMENT_FAILED: DeploymentFailedPayload,
    EventType.APPROVAL_REQUESTED: ApprovalRequestedPayload,
    EventType.APPROVAL_GRANTED: ApprovalGrantedPayload,
    EventType.APPROVAL_REJECTED: ApprovalRejectedPayload,
    EventType.APPROVAL_CHANGES_REQUESTED: ApprovalChangesRequestedPayload,
    EventType.SYSTEM_HEARTBEAT: SystemHeartbeatPayload,
    EventType.CONVERSATION_MESSAGE: ConversationMessagePayload,
    EventType.CONVERSATION_MESSAGE_DELTA: ConversationMessageDeltaPayload,
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
