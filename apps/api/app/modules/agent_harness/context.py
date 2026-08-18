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

from dataclasses import dataclass
from pathlib import Path

from ...templates.software_company import RoleSpec
from ..skill_templates.registry import SkillTemplate
from .budget import HarnessBudget


@dataclass(frozen=True)
class ToolRunContext:
    project_id: str
    task_id: str
    repo_root: Path
    branch_name: str
    role: RoleSpec
    skill_template: SkillTemplate
    stage_kind: str
    harness_enabled: bool
    workspace_ready: bool
    budget: HarnessBudget
