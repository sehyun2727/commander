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


class SpecificationAlreadyExecutingError(CommanderError):
    """Sprint 12 §4.7/§9: `begin-execution` was called for a Specification
    that already has a Mission (`TaskORM.specification_id`) -- each
    approved Specification may start execution exactly once, mirroring the
    one-current-review-candidate policy brief §4.8 already establishes for
    revisions."""

    def __init__(self, specification_id: str) -> None:
        self.specification_id = specification_id
        super().__init__(f"Specification {specification_id!r} has already begun execution")


class StaleRevisionError(CommanderError):
    """Sprint 15 §5/§8: a Workspace preference update's `expected_revision`
    did not match the row's current `revision` -- another tab/write already
    moved the layout forward. The caller must reload the authoritative
    preferences and retry, never silently overwrite (DECISIONS.md #228)."""

    def __init__(self, current_revision: int) -> None:
        self.current_revision = current_revision
        super().__init__(f"Preferences have moved on to revision {current_revision}; reload and retry")


class ToolDeniedError(CommanderError):
    """Sprint 16 Agent Harness: a tool call was rejected by the permission
    intersection (server global policy / RoleSpec.tools / skill-template
    capabilities / stage kind / workspace availability) before it ran.
    Fail-closed by design (DECISIONS.md #233) -- any missing or
    unresolvable term denies the call rather than defaulting to allow."""

    def __init__(self, tool_name: str, reason: str) -> None:
        self.tool_name = tool_name
        self.reason = reason
        super().__init__(f"Tool {tool_name!r} denied: {reason}")


class ToolPathViolationError(CommanderError):
    """Sprint 16 Agent Harness: a tool call's path argument resolved
    outside the Mission's workspace root, traversed via '..', or crossed a
    symlink boundary. Confinement is always enforced via
    `Path.resolve()` + `relative_to()`, never string-prefix matching (see
    `workspace_manager/validation.py`, reused by the harness guard)."""

    def __init__(self, tool_name: str, path: str) -> None:
        self.tool_name = tool_name
        self.path = path
        super().__init__(f"Tool {tool_name!r} rejected path {path!r}: outside workspace root")


class ToolCallMalformedError(CommanderError):
    """Sprint 16 Agent Harness: provider output for a tool call failed
    schema validation (unknown tool name or invalid arguments) even after
    the bounded retry budget (DECISIONS.md #233) was spent."""

    def __init__(self, tool_name: str, attempts: int, detail: str) -> None:
        self.tool_name = tool_name
        self.attempts = attempts
        self.detail = detail
        super().__init__(f"Tool call {tool_name!r} malformed after {attempts} attempt(s): {detail}")


class PatchConflictError(CommanderError):
    """Sprint 16 Agent Harness: `apply_patch`'s optional base-hash/
    expected-content check detected the file changed since the Engineer
    last read it (DECISIONS.md #233's stale-conflict detection)."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"Patch conflict at {path!r}: file content no longer matches the expected base")


class ToolLoopExhaustedError(CommanderError):
    """Sprint 16 Agent Harness (DECISIONS.md #235): a tool loop could not
    reach a completion -- too many consecutive denied or malformed/rejected
    tool calls. Rule #13: never retry forever. `workflow_engine` catches
    this the same way it catches any other stage failure (fails the
    Mission with a visible reason); `BudgetExceededError` remains the
    separate path for exhausting the call-count/wall-time budget itself."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Tool loop could not complete: {reason}")


class SelfCorrectionExhaustedError(CommanderError):
    """Sprint 17 Self-Correction (DECISIONS.md #239): a tool loop's most
    recent `run_validation` kept returning `status="failed"` through
    `MAX_CORRECTION_ATTEMPTS` forced retries and the Employee never
    surrendered either. Rule #13: never retry forever. `workflow_engine`
    fails the Mission with `reason_code="self_correction_exhausted"` --
    distinct from `ToolLoopExhaustedError`, which covers provider
    misbehavior (denied/malformed streaks), not a persistently failing
    validation."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Self-correction exhausted: {reason}")


class EmployeeSurrenderedError(CommanderError):
    """Sprint 17 Self-Correction (DECISIONS.md #239): the Employee
    explicitly emitted `**Unable to Complete:**` rather than continue
    fixing a failing validation (or continue at all). Not a bug or a
    budget/streak exhaustion -- a legitimate, visible stop the Mission
    must still fail with a distinct, honest reason_code
    ("employee_surrendered") rather than being silently treated as a
    normal completion (Rule #18)."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Employee surrendered: {reason}")
