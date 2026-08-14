"""Skill Templates module.

Canonical, immutable, server-owned catalog of Employee skill templates
(Sprint 11 §4.6/§6.3). Not a tool grant system -- see registry.py.
"""

from .registry import (
    DEFAULT_SKILL_TEMPLATE_KEY,
    SKILL_TEMPLATES,
    SKILL_TEMPLATES_BY_KEY,
    SkillTemplate,
)
from .routes import router

__all__ = [
    "DEFAULT_SKILL_TEMPLATE_KEY",
    "SKILL_TEMPLATES",
    "SKILL_TEMPLATES_BY_KEY",
    "SkillTemplate",
    "router",
]
