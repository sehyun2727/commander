"""Canonical, immutable registry of Agent Harness tools (Sprint 16 §4,
DECISIONS.md #233).

Same shape as `skill_templates/registry.py` (Sprint 11) and
`workspace_widgets/registry.py` (Sprint 15): a frozen dataclass tuple plus
a `TOOLS_BY_KEY` lookup, code-only and immutable. This is the *only*
source of what a tool call can mean -- provider output, client input, and
stored `RoleSpec`/skill-template data may only ever *select* a key already
present here, never invent one (Rule #12: tools are granted by the
Template to a Role, nobody else).

Each tool declares the capability it requires (intersected against the
Employee's skill-template `capabilities`, see `permissions.py`) and
whether it mutates the workspace, so the permission resolver and the
audit log can reason about a tool without inspecting its handler.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolDefinition:
    key: str
    title: str
    description: str
    mutates: bool
    requires_capability: str


LIST_REPOSITORY = ToolDefinition(
    key="list_repository",
    title="List Repository",
    description="List files in the mission workspace beneath a given directory.",
    mutates=False,
    requires_capability="repository_tools",
)

READ_FILE = ToolDefinition(
    key="read_file",
    title="Read File",
    description="Read the current content of one file in the mission workspace.",
    mutates=False,
    requires_capability="repository_tools",
)

SEARCH_REPOSITORY = ToolDefinition(
    key="search_repository",
    title="Search Repository",
    description="Search file contents in the mission workspace for a literal substring.",
    mutates=False,
    requires_capability="repository_tools",
)

INSPECT_GIT = ToolDefinition(
    key="inspect_git",
    title="Inspect Git",
    description="View the current diff of the mission's working branch against its base.",
    mutates=False,
    requires_capability="repository_tools",
)

APPLY_PATCH = ToolDefinition(
    key="apply_patch",
    title="Apply Patch",
    description="Write or overwrite files in the mission workspace as complete-content replacements.",
    mutates=True,
    requires_capability="repository_tools",
)

RUN_VALIDATION = ToolDefinition(
    key="run_validation",
    title="Run Validation",
    description="Run a named, template-owned validation profile against the mission workspace inside the sandbox.",
    mutates=False,
    requires_capability="repository_tools",
)

REVERT_LAST_PATCH = ToolDefinition(
    key="revert_last_patch",
    title="Revert Last Patch",
    description="Undo the most recent apply_patch commit on this attempt's branch, back to its previous state.",
    mutates=True,
    requires_capability="repository_tools",
)

TOOLS: tuple[ToolDefinition, ...] = (
    LIST_REPOSITORY,
    READ_FILE,
    SEARCH_REPOSITORY,
    INSPECT_GIT,
    APPLY_PATCH,
    RUN_VALIDATION,
    REVERT_LAST_PATCH,
)
TOOLS_BY_KEY: dict[str, ToolDefinition] = {tool.key: tool for tool in TOOLS}
WRITE_TOOL_KEYS: frozenset[str] = frozenset(tool.key for tool in TOOLS if tool.mutates)
