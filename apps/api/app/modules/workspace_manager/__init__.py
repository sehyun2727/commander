"""Workspace Manager module.

Will implement core.interfaces.workspace_manager.WorkspaceManager. Owns the
git repository: branches, diffs, commits, file changes, patches, and
human-readable summaries. The CEO never sees raw code by default.

Rule: every mutating operation this module performs MUST also publish a
workspace.* event via event_bus — this is how Timeline and other consumers
learn about workspace changes. (See docs/backend/DEPENDENCIES.md — this
rule is currently convention-based, not structurally enforced; flagged as
a risk for Sprint 2.)

Allowed dependencies: event_bus (via interface).

No implementation yet (Sprint 1 defines module boundaries only).
"""
