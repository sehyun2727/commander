"""Enumerates every event type Commander may emit, grouped by domain.

Grouping mirrors docs/ARCHITECTURE.md § "Event Bus" and the domains called
out in Sprint 1: projects, tasks, agents, workspace, models, reviews,
deployments, approvals.
"""

from enum import Enum


class EventType(str, Enum):
    # Projects
    PROJECT_CREATED = "project.created"
    PROJECT_ARCHIVED = "project.archived"

    # Tasks (workflow)
    TASK_CREATED = "task.created"
    TASK_ASSIGNED = "task.assigned"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_RETRIED = "task.retried"
    TASK_CANCELLED = "task.cancelled"
    TASK_STATE_CHANGED = "task.state_changed"

    # Agents
    AGENT_STARTED = "agent.started"
    AGENT_STOPPED = "agent.stopped"
    CODING_STARTED = "agent.coding_started"
    AGENT_STATE_CHANGED = "agent.state_changed"

    # Workspace
    WORKSPACE_FILE_CHANGED = "workspace.file_changed"
    WORKSPACE_COMMITTED = "workspace.committed"
    WORKSPACE_BRANCH_CREATED = "workspace.branch_created"

    # Models / providers
    MODEL_CHANGED = "model.changed"
    PROVIDER_CHANGED = "provider.changed"

    # Reviews
    REVIEW_STARTED = "review.started"
    REVIEW_COMPLETED = "review.completed"
    BUG_FOUND = "review.bug_found"

    # Deployments
    DEPLOYMENT_STARTED = "deployment.started"
    DEPLOYMENT_COMPLETED = "deployment.completed"
    DEPLOYMENT_FAILED = "deployment.failed"

    # Approvals
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_GRANTED = "approval.granted"
    APPROVAL_REJECTED = "approval.rejected"
