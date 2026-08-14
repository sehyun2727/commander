"""Canonical, server-owned catalog of Employee skill templates (Sprint 11
§4.6/§6.3).

A skill template is a named, predefined capability *profile* the CEO may
attach to an Employee at hire time or later -- never an arbitrary tool,
executable string, or capability name the client invents. Until the
Sprint 16 Agent Harness exists, no skill template grants any runtime
capability; selecting one only shapes presentation ("what kind of
specialist is this Employee") and is persisted as data, exactly like
`AgentProfile` today. `RoleSpec.tools` remains the only (currently empty)
whitelist that would ever grant real execution -- a skill template can
never expand it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillTemplate:
    key: str
    title: str
    description: str
    # Presentation-only identifiers, not executable capability grants.
    # A future Harness sprint may give these real meaning; today they are
    # inert data, same as RoleSpec.tools.
    capabilities: tuple[str, ...]


GENERALIST = SkillTemplate(
    key="generalist",
    title="Generalist",
    description="Handles whatever the Role calls for with no specialization bias.",
    capabilities=(),
)

RESEARCH_FOCUSED = SkillTemplate(
    key="research_focused",
    title="Research-Focused",
    description="Leans on thorough investigation and precedent before producing an answer.",
    capabilities=("research",),
)

SPEED_FOCUSED = SkillTemplate(
    key="speed_focused",
    title="Speed-Focused",
    description="Optimizes for fast turnaround on straightforward missions.",
    capabilities=("fast_iteration",),
)

SKILL_TEMPLATES: tuple[SkillTemplate, ...] = (GENERALIST, RESEARCH_FOCUSED, SPEED_FOCUSED)
SKILL_TEMPLATES_BY_KEY: dict[str, SkillTemplate] = {template.key: template for template in SKILL_TEMPLATES}
DEFAULT_SKILL_TEMPLATE_KEY: str = GENERALIST.key
