"""Named failure modes for Commander.

Contracts only — no retry/escalation logic lives here. See
docs/backend/workflow/FAILURE_HANDLING.md for how workflow_engine should
react to each one. Future implementations should raise these specific
types so failure handling can dispatch on exception type, not on parsed
error strings.
"""


class CommanderError(Exception):
    """Base class for every domain-level failure Commander must handle explicitly."""


class AgentTimeoutError(CommanderError):
    """An agent did not report progress within its allotted time."""


class ModelUnavailableError(CommanderError):
    """The requested model/provider could not service a request."""


class WorkspaceConflictError(CommanderError):
    """A workspace mutation could not be applied due to a conflicting change."""


class ReviewRejectedError(CommanderError):
    """A Reviewer agent rejected the work under review."""


class ApprovalRejectedError(CommanderError):
    """The CEO rejected an approval request."""


class SingletonRoleViolation(CommanderError):
    """A second Employee was about to be created for a `singleton=True`
    Role (Sprint 10 §10) -- PM/Reviewer may each have at most one
    Employee at a time; worker Roles like Engineer have no such limit."""

    def __init__(self, role_key: str) -> None:
        self.role_key = role_key
        super().__init__(f"Role {role_key!r} is a singleton and already has an Employee")


class BudgetExceededError(CommanderError):
    """A Mission exceeded one of its token/USD/wall-time budget caps (Rule #13)."""

    def __init__(self, limit_kind: str, limit_value: float, observed_value: float, stage: str) -> None:
        self.limit_kind = limit_kind
        self.limit_value = limit_value
        self.observed_value = observed_value
        self.stage = stage
        super().__init__(f"{limit_kind} budget exceeded before '{stage}': {observed_value} > {limit_value}")


class CTOVacantError(CommanderError):
    """Sprint 12 §4.2: planning was requested but no Employee currently
    occupies the CTO Role. Never falls back to another Role and never
    auto-creates one -- the CEO must hire a CTO first."""

    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        super().__init__("Planning requires an active CTO, and this company has none hired yet")


class ActivePlanningExistsError(CommanderError):
    """Sprint 12 §5.3: this Company already has a non-terminal
    Specification in flight; only one may exist at a time."""

    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        super().__init__("This company already has an active planning run or specification in review")


class PlanningTurnBudgetExhaustedError(CommanderError):
    """Sprint 12 §4.3: the Specification's lifetime planning-turn bound
    (see `modules.planning.orchestrator.MAX_PLANNING_TURNS`) was reached
    without producing a reviewable Specification version."""

    def __init__(self, specification_id: str, max_turns: int) -> None:
        self.specification_id = specification_id
        self.max_turns = max_turns
        super().__init__(f"Planning turn budget ({max_turns}) exhausted for specification {specification_id!r}")


class MalformedProviderOutputError(CommanderError):
    """Sprint 12 §4.12: a provider's structured-output response could not
    be validated even after the bounded retry budget was spent."""

    def __init__(self, stage: str, attempts: int) -> None:
        self.stage = stage
        self.attempts = attempts
        super().__init__(f"Provider returned unusable structured output for '{stage}' after {attempts} attempt(s)")
