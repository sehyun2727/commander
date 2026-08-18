"""Port: workspace/git operations available to the rest of the system.

Sprint 2 wrapped every mutating method in a `@final` template method that
always published a workspace.* event, so a concrete implementation could
never forget to publish. Sprint 5 replaces that shape: the real git
operations this sprint needs (validated multi-file writes with per-file
skip semantics, lazy init, a merge that can legitimately fail, read-only
tree/file access for the Workspace page) don't reduce to "one hook, one
fixed event" — and the caller (`workflow_engine`) already has the mission
context needed to write a good event `reason`, which the manager doesn't.
So this is a plain ABC, matching `core/interfaces/workflow_engine.py`:
concrete implementations are pure git I/O with no EventBus dependency;
`workflow_engine` publishes `workspace.initialized` / `code.changed` /
`branch.merged` itself. See docs/DECISIONS.md ("Sprint 5").

⚑ No AI-generated code is ever executed through this port or its
implementations — write/read/diff/merge only. Enforcing that is a caller
responsibility (the Reviewer audits statically); this port doesn't run
anything by construction, since none of its methods invoke workspace
content.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class WriteResult:
    """Outcome of a validated multi-file write. Invalid files are skipped,
    not fatal — the caller continues with whatever was valid."""

    written: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (path, reason)


@dataclass(frozen=True)
class CommitResult:
    commit_sha: str
    files_added: int
    files_modified: int
    files_deleted: int
    additions: int
    deletions: int


@dataclass(frozen=True)
class FileEntry:
    path: str


@dataclass(frozen=True)
class MergeRecord:
    commit_sha: str
    subject: str
    merged_at: str


class WorkspaceManager(ABC):
    """One real git repo per company. Implementations own only git I/O —
    no EventBus, no knowledge of missions/tasks."""

    @abstractmethod
    def repo_root(self, project_id: str) -> Path:
        """The confined filesystem root a tool call's paths must resolve
        within (Sprint 16 Agent Harness `ToolRunContext.repo_root`). Never
        used for I/O by this port itself -- callers pass it to
        `agent_harness.guards.guard_path` for confinement checks, the same
        root every other method here already writes/reads under."""
        ...

    @abstractmethod
    async def ensure_initialized(self, project_id: str) -> bool:
        """Lazily init the repo on first use (README committed to main).
        Returns True if this call performed the init, False if it already
        existed — so the caller knows whether to publish
        workspace.initialized."""
        ...

    @abstractmethod
    async def create_branch(self, project_id: str, branch_name: str) -> None:
        """Idempotent: no-op if the branch already exists."""
        ...

    @abstractmethod
    async def write_files(
        self, project_id: str, branch_name: str, files: dict[str, str]
    ) -> WriteResult:
        """Validate + write each path (relative-only, contained in the repo,
        never under .git/, ≤256KB, text/no-NUL). Invalid entries are
        skipped with a reason, not raised."""
        ...

    @abstractmethod
    async def commit(
        self, project_id: str, branch_name: str, message: str
    ) -> CommitResult:
        """Commit whatever is staged on branch_name."""
        ...

    @abstractmethod
    async def diff(
        self, project_id: str, branch_name: str, *, max_chars: int = 12000
    ) -> tuple[str, bool]:
        """Unified diff of branch_name against main. Returns
        (diff_text, was_truncated)."""
        ...

    @abstractmethod
    async def diff_stats(self, project_id: str, branch_name: str) -> CommitResult:
        """Aggregate branch-vs-main stats (files added/modified/deleted,
        additions/deletions) plus the branch's current HEAD sha. Sprint 16
        §4.14/DECISIONS.md #234: an Agent Harness tool loop can call
        `apply_patch` more than once per attempt, each committing
        immediately, so a single `commit()`'s `CommitResult` no longer
        represents the whole attempt -- callers that need one summary
        figure for a multi-commit attempt use this instead of trusting the
        last `commit()` call."""
        ...

    @abstractmethod
    async def merge(self, project_id: str, branch_name: str) -> str:
        """Fast-forward/merge branch_name into main. Returns the resulting
        commit sha on main. Raises WorkspaceConflictError on failure — no
        auto-resolution."""
        ...

    @abstractmethod
    async def list_tree(
        self, project_id: str, ref: str = "main"
    ) -> list[FileEntry]:
        """Flat file listing at ref (Workspace page builds any tree
        grouping client-side)."""
        ...

    @abstractmethod
    async def read_file(self, project_id: str, path: str, ref: str = "main") -> str:
        """Read-only file content at ref, for the Workspace file viewer."""
        ...

    @abstractmethod
    async def recent_merges(
        self, project_id: str, limit: int = 10
    ) -> list[MergeRecord]:
        """Most recent merge commits on main, for the Workspace page."""
        ...
