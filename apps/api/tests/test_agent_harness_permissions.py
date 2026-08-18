from __future__ import annotations

import dataclasses

import pytest

from app.core.errors import ToolDeniedError
from app.modules.agent_harness.permissions import authorize_tool_call, resolve_permitted_tools
from app.modules.agent_harness.registry import TOOLS_BY_KEY
from app.modules.skill_templates.registry import SkillTemplate
from app.templates.software_company import ENGINEER, RoleSpec

ALL_TOOL_KEYS = tuple(TOOLS_BY_KEY)
GRANTED_TEMPLATE = SkillTemplate(
    key="granted_test_template",
    title="Granted",
    description="test-only template with repository_tools",
    capabilities=("repository_tools",),
)
# Phase 3 grants every stock SkillTemplate "repository_tools" for real, so
# the missing-capability test needs an explicitly empty template rather
# than relying on GENERALIST being inert.
EMPTY_TEMPLATE = SkillTemplate(
    key="empty_test_template",
    title="Empty",
    description="test-only template with no capabilities",
    capabilities=(),
)


def _role_with_tools(tools: tuple[str, ...]) -> RoleSpec:
    return dataclasses.replace(ENGINEER, tools=tools)


def test_full_grant_returns_exactly_the_intersected_set():
    role = _role_with_tools(ALL_TOOL_KEYS)
    permitted = resolve_permitted_tools(
        role=role,
        skill_template=GRANTED_TEMPLATE,
        stage_kind="produce",
        harness_enabled=True,
        workspace_ready=True,
    )
    assert permitted == frozenset(ALL_TOOL_KEYS)


def test_empty_role_tools_denies_everything():
    role = _role_with_tools(())
    permitted = resolve_permitted_tools(
        role=role,
        skill_template=GRANTED_TEMPLATE,
        stage_kind="produce",
        harness_enabled=True,
        workspace_ready=True,
    )
    assert permitted == frozenset()


def test_missing_capability_denies_everything():
    role = _role_with_tools(ALL_TOOL_KEYS)
    permitted = resolve_permitted_tools(
        role=role,
        skill_template=EMPTY_TEMPLATE,
        stage_kind="produce",
        harness_enabled=True,
        workspace_ready=True,
    )
    assert permitted == frozenset()


@pytest.mark.parametrize("stage_kind", ["plan", "review", "unknown"])
def test_non_produce_stage_denies_everything(stage_kind):
    role = _role_with_tools(ALL_TOOL_KEYS)
    permitted = resolve_permitted_tools(
        role=role,
        skill_template=GRANTED_TEMPLATE,
        stage_kind=stage_kind,
        harness_enabled=True,
        workspace_ready=True,
    )
    assert permitted == frozenset()


def test_harness_disabled_denies_everything():
    role = _role_with_tools(ALL_TOOL_KEYS)
    permitted = resolve_permitted_tools(
        role=role,
        skill_template=GRANTED_TEMPLATE,
        stage_kind="produce",
        harness_enabled=False,
        workspace_ready=True,
    )
    assert permitted == frozenset()


def test_workspace_not_ready_denies_everything():
    role = _role_with_tools(ALL_TOOL_KEYS)
    permitted = resolve_permitted_tools(
        role=role,
        skill_template=GRANTED_TEMPLATE,
        stage_kind="produce",
        harness_enabled=True,
        workspace_ready=False,
    )
    assert permitted == frozenset()


def test_unknown_tool_name_in_role_tools_is_ignored_not_granted():
    role = _role_with_tools(("read_file", "definitely_not_a_real_tool"))
    permitted = resolve_permitted_tools(
        role=role,
        skill_template=GRANTED_TEMPLATE,
        stage_kind="produce",
        harness_enabled=True,
        workspace_ready=True,
    )
    assert permitted == frozenset({"read_file"})


def test_authorize_tool_call_allows_permitted_tool():
    role = _role_with_tools(("read_file",))
    authorize_tool_call(
        "read_file",
        role=role,
        skill_template=GRANTED_TEMPLATE,
        stage_kind="produce",
        harness_enabled=True,
        workspace_ready=True,
    )


def test_authorize_tool_call_denies_unpermitted_tool():
    role = _role_with_tools(())
    with pytest.raises(ToolDeniedError):
        authorize_tool_call(
            "read_file",
            role=role,
            skill_template=GRANTED_TEMPLATE,
            stage_kind="produce",
            harness_enabled=True,
            workspace_ready=True,
        )


def test_authorize_tool_call_denies_unknown_tool_name():
    role = _role_with_tools(ALL_TOOL_KEYS)
    with pytest.raises(ToolDeniedError):
        authorize_tool_call(
            "run_shell",
            role=role,
            skill_template=GRANTED_TEMPLATE,
            stage_kind="produce",
            harness_enabled=True,
            workspace_ready=True,
        )
