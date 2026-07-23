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
