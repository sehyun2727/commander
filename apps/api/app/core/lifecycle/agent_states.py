"""Agent lifecycle: states and allowed transitions.

See docs/backend/workflow/AGENT_LIFECYCLE.md for the diagram and rationale.
"""

from enum import Enum


class AgentState(str, Enum):
    IDLE = "idle"
    ASSIGNED = "assigned"
    PLANNING = "planning"
    WORKING = "working"
    WAITING_REVIEW = "waiting_review"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


AGENT_TRANSITIONS: dict[AgentState, set[AgentState]] = {
    AgentState.IDLE: {AgentState.ASSIGNED},
    AgentState.ASSIGNED: {AgentState.PLANNING, AgentState.FAILED},
    AgentState.PLANNING: {AgentState.WORKING, AgentState.BLOCKED, AgentState.FAILED},
    AgentState.WORKING: {AgentState.WAITING_REVIEW, AgentState.BLOCKED, AgentState.FAILED},
    AgentState.WAITING_REVIEW: {AgentState.WORKING, AgentState.COMPLETED, AgentState.BLOCKED},
    AgentState.BLOCKED: {AgentState.PLANNING, AgentState.WORKING, AgentState.FAILED},
    AgentState.COMPLETED: {AgentState.IDLE},
    AgentState.FAILED: {AgentState.IDLE},
}
