"""Task lifecycle: states and allowed transitions.

See docs/backend/workflow/TASK_LIFECYCLE.md for the diagram and rationale.
"""

from enum import Enum


class TaskState(str, Enum):
    CREATED = "created"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    PENDING_APPROVAL = "pending_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"  # Sprint 5: merge-to-main failed on approve; no auto-resolution


TASK_TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.CREATED: {TaskState.ASSIGNED, TaskState.CANCELLED},
    TaskState.ASSIGNED: {TaskState.IN_PROGRESS, TaskState.CANCELLED},
    TaskState.IN_PROGRESS: {
        TaskState.IN_REVIEW,
        TaskState.FAILED,
        TaskState.CANCELLED,
        TaskState.BLOCKED,  # Sprint 9: orphan recovery on restart, budget guard
    },
    TaskState.IN_REVIEW: {
        TaskState.PENDING_APPROVAL,
        TaskState.COMPLETED,
        TaskState.IN_PROGRESS,  # changes requested -> rework
        TaskState.FAILED,  # rejected beyond rework limit
        TaskState.CANCELLED,  # Sprint 9: CEO can cancel mid-review
        TaskState.BLOCKED,  # Sprint 9: orphan recovery on restart, budget guard
    },
    TaskState.PENDING_APPROVAL: {
        TaskState.COMPLETED,
        TaskState.IN_PROGRESS,  # rejected -> rework
        TaskState.CANCELLED,  # rejected -> abandon
        TaskState.BLOCKED,  # approved but merge to main failed
    },
    TaskState.FAILED: {TaskState.RETRYING, TaskState.CANCELLED},
    TaskState.RETRYING: {TaskState.ASSIGNED},
    TaskState.COMPLETED: set(),
    TaskState.CANCELLED: set(),
    TaskState.BLOCKED: set(),
}
