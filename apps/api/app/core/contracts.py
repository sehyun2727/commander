"""Domain contracts shared across modules but not tied to any one event or
table — shared infrastructure like core.db_models and core.events, so every
module may depend on it directly without violating "modules never import
each other's internals" (the rule is about module-to-module coupling, not
access to the persistence/contracts floor).

AgentProfile is the CEO-editable personality configuration for one
Employee. It is persisted verbatim as JSON on `AgentORM.profile`; the
prompt actually sent to a provider is never stored — `prompt_builder.build()`
turns a profile + a role contract into a system prompt at call time, so
profile edits take effect on the very next call.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from .lifecycle.agent_states import AgentState
from .lifecycle.task_states import TaskState

CUSTOM_INSTRUCTIONS_MAX_LEN = 500


class Personality(str, Enum):
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    DIRECT = "direct"
    CONSERVATIVE = "conservative"


class WorkingStyle(str, Enum):
    FAST = "fast"
    BALANCED = "balanced"
    DETAIL_ORIENTED = "detail_oriented"


class DecisionStyle(str, Enum):
    RISK_AVOIDING = "risk_avoiding"
    BALANCED = "balanced"
    EXPERIMENTAL = "experimental"


class AgentProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    name: str
    role: str  # "pm" | "engineer" | "reviewer" -- mirrors AgentORM.role
    personality: Personality = Personality.PROFESSIONAL
    working_style: WorkingStyle = WorkingStyle.BALANCED
    decision_style: DecisionStyle = DecisionStyle.BALANCED
    custom_instructions: str = Field(default="", max_length=CUSTOM_INSTRUCTIONS_MAX_LEN)
    # Agent-level model override (three-tier resolution: agent > role >
    # registry default — see provider_gateway.gateway.RoutedProviderGateway).
    # Never a provider switch, only a model choice within the company's
    # active provider.
    model_ref: str | None = None


class StatusWord(str, Enum):
    """The single source of truth for external status vocabulary (UX_SPEC
    §1). Internal lifecycle states (TaskState, AgentState) never reach the
    CEO directly -- every render site maps through one of the two dicts
    below to a StatusWord token first. The token -> copy text (and, if we
    ever ship i18n, translations) lives in the frontend's StatusWord
    component, not here: this module only owns *which* token a given
    internal state maps to, not what it says.
    """

    PLANNING = "planning"
    DEVELOPING = "developing"
    REVIEWING = "reviewing"
    NEEDS_DECISION = "needs_decision"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    IDLE = "idle"


TASK_STATE_STATUS_WORD: dict[TaskState, StatusWord] = {
    TaskState.CREATED: StatusWord.PLANNING,
    TaskState.ASSIGNED: StatusWord.PLANNING,
    TaskState.IN_PROGRESS: StatusWord.DEVELOPING,
    TaskState.IN_REVIEW: StatusWord.REVIEWING,
    TaskState.PENDING_APPROVAL: StatusWord.NEEDS_DECISION,
    TaskState.RETRYING: StatusWord.DEVELOPING,
    TaskState.COMPLETED: StatusWord.COMPLETED,
    TaskState.FAILED: StatusWord.FAILED,
    TaskState.CANCELLED: StatusWord.CANCELLED,
    TaskState.BLOCKED: StatusWord.BLOCKED,
}

AGENT_STATE_STATUS_WORD: dict[AgentState, StatusWord] = {
    AgentState.IDLE: StatusWord.IDLE,
    AgentState.ASSIGNED: StatusWord.PLANNING,
    AgentState.PLANNING: StatusWord.PLANNING,
    AgentState.WORKING: StatusWord.DEVELOPING,
    AgentState.WAITING_REVIEW: StatusWord.REVIEWING,
    AgentState.BLOCKED: StatusWord.BLOCKED,
    AgentState.COMPLETED: StatusWord.COMPLETED,
    AgentState.FAILED: StatusWord.FAILED,
}
