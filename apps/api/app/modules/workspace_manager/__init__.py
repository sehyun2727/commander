"""Workspace Manager module.

Implements `core.interfaces.workspace_manager.WorkspaceManager` against a
real local git repository per company (`LocalGitWorkspaceManager`). Pure
git I/O -- no EventBus dependency; `workflow_engine` publishes
`workspace.initialized` / `code.changed` / `branch.merged` itself, since
it has the mission context needed to write a good `reason`. See
docs/DECISIONS.md ("Sprint 5", #87).

⚑ No AI-generated code is ever executed here or anywhere downstream of
this module -- write/read/diff/merge only.
"""

from .local_git import LocalGitWorkspaceManager

__all__ = ["LocalGitWorkspaceManager"]
