"""Server-issued run context for Agent Harness tool calls (Sprint 16 §4.1,
DECISIONS.md #233).

A `ToolRunContext` is constructed once per tool loop, entirely from
server-trusted data (the Mission's `project_id`/`task_id`, the resolved
workspace root, the acting Employee's `RoleSpec`/`SkillTemplate`, the
current pipeline `stage_kind`, and a `HarnessBudget`) -- never from
provider output. Tool handlers (Phase 2) receive this context plus
already-schema-validated arguments; they never derive identity, workspace
location, or permission facts from the provider's own text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ...templates.software_company import RoleSpec
from ..skill_templates.registry import SkillTemplate
from .budget import HarnessBudget


@dataclass(frozen=True)
class ToolRunContext:
    project_id: str
    task_id: str
    agent_id: str
    repo_root: Path
    branch_name: str
    role: RoleSpec
    skill_template: SkillTemplate
    stage_kind: str
    harness_enabled: bool
    workspace_ready: bool
    budget: HarnessBudget
    # Sprint 17 §4.7 (DECISIONS.md #239): the branch's HEAD sha at the
    # moment it was created for this attempt, before any `apply_patch`
    # commit -- `revert_last_patch`'s rollback floor. A tool loop must
    # never reset past this, even after every apply_patch commit has been
    # unwound.
    branch_base_sha: str


@dataclass
class LoopState:
    """Orchestrator-owned mutable state for one tool-loop attempt (Sprint
    17 §4.16, DECISIONS.md #239) -- deliberately *not* part of the frozen
    `ToolRunContext` above, since it changes on nearly every tool call.
    Threaded through `dispatch_tool_call` as an optional kwarg so
    `apply_patch`/`run_validation` can update it directly from the
    `CommitResult`/`CheckResult` they already have in hand, rather than
    the orchestrator re-deriving the same facts with a second git/sandbox
    call."""

    last_validation_status: str | None = None
    correction_attempts: int = 0
    first_correction_emitted: bool = False
    apply_patch_commit_history: list[str] = field(default_factory=list)
