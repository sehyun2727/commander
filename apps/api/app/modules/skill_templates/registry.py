"""Canonical, server-owned catalog of Employee skill templates (Sprint 11
§4.6/§6.3).

A skill template is a named, predefined capability *profile* the CEO may
attach to an Employee at hire time or later -- never an arbitrary tool,
executable string, or capability name the client invents. Before Sprint
16, no skill template granted any runtime capability; selecting one only
shaped presentation. Sprint 16's Agent Harness gives `"repository_tools"`
real meaning: it is one term of the fail-closed permission intersection
(`agent_harness.permissions.resolve_permitted_tools`) alongside
`RoleSpec.tools`, harness_enabled, stage_kind, and workspace_ready --
every template below grants it so tool access isn't accidentally
specialization-gated, since Sprint 16 doesn't scope per-skill-template
tool differentiation (DECISIONS.md #235). `RoleSpec.tools` remains the
Role-level whitelist a skill template can never expand.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillTemplate:
    key: str
    title: str
    description: str
    # `"repository_tools"` is the one capability with real meaning today
    # (Sprint 16 Agent Harness); any other value remains inert
    # presentation-only data, same as before Sprint 16.
    capabilities: tuple[str, ...]


GENERALIST = SkillTemplate(
    key="generalist",
    title="Generalist",
    description="Handles whatever the Role calls for with no specialization bias.",
    capabilities=("repository_tools",),
)

RESEARCH_FOCUSED = SkillTemplate(
    key="research_focused",
    title="Research-Focused",
    description="Leans on thorough investigation and precedent before producing an answer.",
    capabilities=("research", "repository_tools"),
)

SPEED_FOCUSED = SkillTemplate(
    key="speed_focused",
    title="Speed-Focused",
    description="Optimizes for fast turnaround on straightforward missions.",
    capabilities=("fast_iteration", "repository_tools"),
)

SKILL_TEMPLATES: tuple[SkillTemplate, ...] = (GENERALIST, RESEARCH_FOCUSED, SPEED_FOCUSED)
SKILL_TEMPLATES_BY_KEY: dict[str, SkillTemplate] = {template.key: template for template in SKILL_TEMPLATES}
DEFAULT_SKILL_TEMPLATE_KEY: str = GENERALIST.key
