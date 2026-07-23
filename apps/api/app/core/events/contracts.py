"""Concrete event contracts, grouped by domain.

Every event here is a frozen dataclass extending Event. These are pure data
contracts — no behavior, no persistence, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

from .base import Event
from .types import EventType
from ..lifecycle.agent_states import AgentState
from ..lifecycle.task_states import TaskState


# --- Projects ---------------------------------------------------------------

@dataclass(frozen=True, kw_only=True)
class ProjectCreated(Event):
    type: EventType = EventType.PROJECT_CREATED
    name: str = ""


@dataclass(frozen=True, kw_only=True)
class ProjectArchived(Event):
    type: EventType = EventType.PROJECT_ARCHIVED


# --- Tasks (workflow) --------------------------------------------------------

@dataclass(frozen=True, kw_only=True)
class TaskCreated(Event):
    type: EventType = EventType.TASK_CREATED
    task_id: str = ""
    title: str = ""
    priority: str = "normal"  # PM-assigned: "low" | "normal" | "high" | "critical"


@dataclass(frozen=True, kw_only=True)
class TaskAssigned(Event):
    type: EventType = EventType.TASK_ASSIGNED
    task_id: str = ""
    agent_id: str = ""
    attempt: int = 1


@dataclass(frozen=True, kw_only=True)
class TaskStarted(Event):
    """Execution began (ASSIGNED -> IN_PROGRESS). Fired for every task type;
    CodingStarted is an additional, more specific event for coding work."""

    type: EventType = EventType.TASK_STARTED
    task_id: str = ""
    agent_id: str = ""


@dataclass(frozen=True, kw_only=True)
class TaskCompleted(Event):
    type: EventType = EventType.TASK_COMPLETED
    task_id: str = ""


@dataclass(frozen=True, kw_only=True)
class TaskFailed(Event):
    type: EventType = EventType.TASK_FAILED
    task_id: str = ""
    reason: str = ""


@dataclass(frozen=True, kw_only=True)
class TaskRetried(Event):
    type: EventType = EventType.TASK_RETRIED
    task_id: str = ""
    attempt: int = 1
    reason: str = ""


@dataclass(frozen=True, kw_only=True)
class TaskCancelled(Event):
    type: EventType = EventType.TASK_CANCELLED
    task_id: str = ""
    reason: str | None = None


@dataclass(frozen=True, kw_only=True)
class TaskStateChanged(Event):
    """Low-level completeness net: fires on every task transition, so
    monitoring/progress tooling never depends on the curated named events
    above being exhaustive. Timeline still consumes the named events for
    CEO narrative, not this one."""

    type: EventType = EventType.TASK_STATE_CHANGED
    task_id: str = ""
    previous_state: TaskState = TaskState.CREATED
    new_state: TaskState = TaskState.CREATED


# --- Agents -------------------------------------------------------------------

@dataclass(frozen=True, kw_only=True)
class AgentStarted(Event):
    type: EventType = EventType.AGENT_STARTED
    agent_id: str = ""
    role: str = ""


@dataclass(frozen=True, kw_only=True)
class AgentStopped(Event):
    type: EventType = EventType.AGENT_STOPPED
    agent_id: str = ""


@dataclass(frozen=True, kw_only=True)
class AgentStateChanged(Event):
    """Low-level completeness net, mirroring TaskStateChanged."""

    type: EventType = EventType.AGENT_STATE_CHANGED
    agent_id: str = ""
    previous_state: AgentState = AgentState.IDLE
    new_state: AgentState = AgentState.IDLE


@dataclass(frozen=True, kw_only=True)
class CodingStarted(Event):
    type: EventType = EventType.CODING_STARTED
    agent_id: str = ""
    task_id: str = ""


# --- Workspace ------------------------------------------------------------------

@dataclass(frozen=True, kw_only=True)
class WorkspaceFileChanged(Event):
    type: EventType = EventType.WORKSPACE_FILE_CHANGED
    path: str = ""
    change_kind: str = ""  # "added" | "modified" | "deleted"


@dataclass(frozen=True, kw_only=True)
class WorkspaceCommitted(Event):
    type: EventType = EventType.WORKSPACE_COMMITTED
    commit_sha: str = ""
    summary: str = ""


@dataclass(frozen=True, kw_only=True)
class WorkspaceBranchCreated(Event):
    type: EventType = EventType.WORKSPACE_BRANCH_CREATED
    branch_name: str = ""


# --- Models / providers ------------------------------------------------------------

@dataclass(frozen=True, kw_only=True)
class ModelChanged(Event):
    type: EventType = EventType.MODEL_CHANGED
    previous_model: str = ""
    new_model: str = ""


@dataclass(frozen=True, kw_only=True)
class ProviderChanged(Event):
    type: EventType = EventType.PROVIDER_CHANGED
    previous_provider: str = ""
    new_provider: str = ""


# --- Reviews ----------------------------------------------------------------------

@dataclass(frozen=True, kw_only=True)
class ReviewStarted(Event):
    type: EventType = EventType.REVIEW_STARTED
    task_id: str = ""
    reviewer_agent_id: str = ""


@dataclass(frozen=True, kw_only=True)
class ReviewCompleted(Event):
    type: EventType = EventType.REVIEW_COMPLETED
    task_id: str = ""
    outcome: str = ""  # "approved" | "changes_requested"


@dataclass(frozen=True, kw_only=True)
class BugFound(Event):
    type: EventType = EventType.BUG_FOUND
    task_id: str = ""
    description: str = ""


# --- Deployments -------------------------------------------------------------------

@dataclass(frozen=True, kw_only=True)
class DeploymentStarted(Event):
    type: EventType = EventType.DEPLOYMENT_STARTED
    deployment_id: str = ""


@dataclass(frozen=True, kw_only=True)
class DeploymentCompleted(Event):
    type: EventType = EventType.DEPLOYMENT_COMPLETED
    deployment_id: str = ""


@dataclass(frozen=True, kw_only=True)
class DeploymentFailed(Event):
    type: EventType = EventType.DEPLOYMENT_FAILED
    deployment_id: str = ""
    reason: str = ""


# --- Approvals -------------------------------------------------------------------

@dataclass(frozen=True, kw_only=True)
class ApprovalRequested(Event):
    type: EventType = EventType.APPROVAL_REQUESTED
    approval_id: str = ""
    subject: str = ""  # e.g. "provider_change", "production_deployment"


@dataclass(frozen=True, kw_only=True)
class ApprovalGranted(Event):
    type: EventType = EventType.APPROVAL_GRANTED
    approval_id: str = ""


@dataclass(frozen=True, kw_only=True)
class ApprovalRejected(Event):
    type: EventType = EventType.APPROVAL_REJECTED
    approval_id: str = ""
    reason: str | None = None
