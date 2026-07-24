"""Enumerates every event type Commander may emit, grouped by domain.

Grouping mirrors docs/ARCHITECTURE.md § "Event Bus" and the Sprint 3 domain
list: project, agent, task, workspace, approval, workflow, model, system,
conversation.
"""

from enum import Enum


class EventType(str, Enum):
    # Projects (Company)
    PROJECT_CREATED = "project.created"
    PROJECT_ARCHIVED = "project.archived"

    # Tasks (Missions)
    TASK_CREATED = "task.created"
    TASK_ASSIGNED = "task.assigned"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_RETRIED = "task.retried"
    TASK_CANCELLED = "task.cancelled"
    TASK_STATE_CHANGED = "task.state_changed"

    # Agents (Employees)
    AGENT_CREATED = "agent.created"
    AGENT_STARTED = "agent.started"
    AGENT_STOPPED = "agent.stopped"
    AGENT_STATE_CHANGED = "agent.state_changed"
    AGENT_PROFILE_UPDATED = "agent.profile_updated"
    CODING_STARTED = "agent.coding_started"

    # Workspace (Workspace/Repository)
    WORKSPACE_FILE_CHANGED = "workspace.file_changed"
    WORKSPACE_COMMITTED = "workspace.committed"
    WORKSPACE_BRANCH_CREATED = "workspace.branch_created"

    # Models / providers (Company Settings)
    MODEL_CHANGED = "model.changed"
    PROVIDER_CHANGED = "provider.changed"
    PROVIDER_RETRIED = "provider.retried"

    # Workflow (planning / review / deployment)
    REVIEW_STARTED = "workflow.review_started"
    REVIEW_COMPLETED = "workflow.review_completed"
    BUG_FOUND = "workflow.bug_found"
    DEPLOYMENT_STARTED = "workflow.deployment_started"
    DEPLOYMENT_COMPLETED = "workflow.deployment_completed"
    DEPLOYMENT_FAILED = "workflow.deployment_failed"

    # Approvals (CEO Decisions)
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_GRANTED = "approval.granted"
    APPROVAL_REJECTED = "approval.rejected"
    APPROVAL_CHANGES_REQUESTED = "approval.changes_requested"

    # System
    SYSTEM_HEARTBEAT = "system.heartbeat"

    # Conversation (Meetings)
    CONVERSATION_MESSAGE = "conversation.message"
    CONVERSATION_MESSAGE_DELTA = "conversation.message.delta"
