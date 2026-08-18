from __future__ import annotations

import dataclasses

import pytest

from app.modules.agent_harness.registry import TOOLS, TOOLS_BY_KEY, WRITE_TOOL_KEYS, ToolDefinition


def test_registry_is_immutable_frozen_dataclass():
    with pytest.raises(dataclasses.FrozenInstanceError):
        TOOLS[0].key = "hacked"  # type: ignore[misc]


def test_tools_by_key_matches_tools_tuple():
    assert set(TOOLS_BY_KEY) == {tool.key for tool in TOOLS}
    for key, tool in TOOLS_BY_KEY.items():
        assert tool.key == key


def test_expected_six_tool_set():
    assert {tool.key for tool in TOOLS} == {
        "list_repository",
        "read_file",
        "search_repository",
        "inspect_git",
        "apply_patch",
        "run_validation",
    }


def test_only_apply_patch_mutates():
    assert WRITE_TOOL_KEYS == {"apply_patch"}


def test_every_tool_requires_repository_tools_capability():
    for tool in TOOLS:
        assert tool.requires_capability == "repository_tools"


def test_no_shell_or_arbitrary_command_tool_exists():
    forbidden_keys = {"run_shell", "execute", "shell", "run_command", "exec"}
    assert forbidden_keys.isdisjoint(TOOLS_BY_KEY)


def test_tool_definition_is_frozen():
    tool = ToolDefinition(key="x", title="X", description="d", mutates=False, requires_capability="c")
    with pytest.raises(dataclasses.FrozenInstanceError):
        tool.mutates = True  # type: ignore[misc]
