"""Lifecycle contracts: the valid states and transitions for tasks and
agents. Pure data + validation — no persistence, no orchestration. Any
future workflow_engine/agent_runtime implementation should route every
state change through `transition()` rather than mutating state directly.
"""

from .agent_states import AGENT_TRANSITIONS, AgentState
from .state_machine import InvalidTransition, transition
from .task_states import TASK_TRANSITIONS, TaskState

__all__ = [
    "AgentState",
    "AGENT_TRANSITIONS",
    "TaskState",
    "TASK_TRANSITIONS",
    "transition",
    "InvalidTransition",
]
