"""Permission intersection for Agent Harness tool calls (Sprint 16 §4.4,
DECISIONS.md #233).

Final tool permission is always an intersection of every term below.
A missing, unresolvable, or `False` term always narrows the result --
this module never defaults to allow:

    server global policy (`harness_enabled`)
        ∩ RoleSpec.tools (template-granted whitelist, Rule #12)
        ∩ skill-template capabilities (Employee's configured specialization)
        ∩ stage kind ("produce" only -- never during "plan"/"review",
          preserving the planning-stage non-mutation guarantee)
        ∩ workspace availability (`workspace_ready`)
"""

from __future__ import annotations

from ...core.errors import ToolDeniedError
from ...templates.software_company import RoleSpec
from ..skill_templates.registry import SkillTemplate
from .registry import TOOLS_BY_KEY

# Tools only ever run during the pipeline's "produce" stage (Rule #16: this
# is workflow-stage semantics, not a role-identity branch). "plan" and
# "review" stages never get tool access, regardless of RoleSpec.tools.
ELIGIBLE_STAGE_KINDS: frozenset[str] = frozenset({"produce"})


def resolve_permitted_tools(
    *,
    role: RoleSpec,
    skill_template: SkillTemplate,
    stage_kind: str,
    harness_enabled: bool,
    workspace_ready: bool,
) -> frozenset[str]:
    """The set of tool keys this Employee may call right now."""
    if not harness_enabled or not workspace_ready or stage_kind not in ELIGIBLE_STAGE_KINDS:
        return frozenset()
    role_tools = frozenset(role.tools)
    template_capabilities = frozenset(skill_template.capabilities)
    permitted: set[str] = set()
    for tool_key in role_tools:
        tool = TOOLS_BY_KEY.get(tool_key)
        if tool is None:
            continue  # unknown tool name in RoleSpec.tools: never grant it
        if tool.requires_capability in template_capabilities:
            permitted.add(tool_key)
    return frozenset(permitted)


def authorize_tool_call(
    tool_name: str,
    *,
    role: RoleSpec,
    skill_template: SkillTemplate,
    stage_kind: str,
    harness_enabled: bool,
    workspace_ready: bool,
) -> None:
    """Raise `ToolDeniedError` unless `tool_name` is currently permitted.
    Call this immediately before every tool handler invocation (not just
    once per loop) -- `stage_kind`/`workspace_ready` can change between
    calls within the same tool loop."""
    if tool_name not in TOOLS_BY_KEY:
        raise ToolDeniedError(tool_name, "unknown tool")
    permitted = resolve_permitted_tools(
        role=role,
        skill_template=skill_template,
        stage_kind=stage_kind,
        harness_enabled=harness_enabled,
        workspace_ready=workspace_ready,
    )
    if tool_name not in permitted:
        raise ToolDeniedError(
            tool_name,
            "not permitted by the current role/skill-template/stage/workspace intersection",
        )
