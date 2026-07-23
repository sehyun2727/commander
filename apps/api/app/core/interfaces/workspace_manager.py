"""Port: workspace/git operations available to the rest of the system.

Sprint 1 shipped this as a pure ABC and flagged a gap: nothing stopped an
implementation from mutating the workspace without publishing the required
workspace.* event. Sprint 2 resolves that structurally (see
docs/backend/workflow/WORKSPACE_CONTRACT.md): the public methods below are
concrete and always publish after calling an abstract `_do_*` hook, so a
concrete implementation only ever supplies the git logic — it cannot
supply (or skip) the event publish, because it never touches that code
path. Read-only methods (diff, summarize) stay simple pass-throughs; they
don't mutate anything, so no event is owed for them.

`@final` marks the public methods as not-to-be-overridden. Python doesn't
enforce this at runtime — a static type checker (mypy/pyright) in CI does.
Wiring that check up is a Sprint 3 suggestion, not done here.
"""

from abc import ABC, abstractmethod
from typing import final

from ..events.contracts import WorkspaceBranchCreated, WorkspaceCommitted
from .event_bus import EventBus


class WorkspaceManager(ABC):
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    @final
    def create_branch(self, project_id: str, branch_name: str) -> None:
        """Create a branch, then always publish WorkspaceBranchCreated."""
        self._do_create_branch(project_id, branch_name)
        self._event_bus.publish(
            WorkspaceBranchCreated(project_id=project_id, branch_name=branch_name)
        )

    @final
    def commit(self, project_id: str, message: str) -> str:
        """Commit staged changes, then always publish WorkspaceCommitted."""
        commit_sha = self._do_commit(project_id, message)
        self._event_bus.publish(
            WorkspaceCommitted(project_id=project_id, commit_sha=commit_sha, summary=message)
        )
        return commit_sha

    def diff(self, project_id: str, branch_name: str) -> str:
        """Read-only: return the diff for a branch (Workspace advanced view)."""
        return self._do_diff(project_id, branch_name)

    def summarize(self, project_id: str, branch_name: str) -> str:
        """Read-only: human-readable summary (Workspace default view) — the
        CEO should never be forced to read source code."""
        return self._do_summarize(project_id, branch_name)

    # --- Hooks a concrete implementation must supply. No git logic here. ---

    @abstractmethod
    def _do_create_branch(self, project_id: str, branch_name: str) -> None: ...

    @abstractmethod
    def _do_commit(self, project_id: str, message: str) -> str: ...

    @abstractmethod
    def _do_diff(self, project_id: str, branch_name: str) -> str: ...

    @abstractmethod
    def _do_summarize(self, project_id: str, branch_name: str) -> str: ...
