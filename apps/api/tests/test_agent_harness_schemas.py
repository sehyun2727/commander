from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.agent_harness.registry import TOOLS_BY_KEY
from app.modules.agent_harness.schemas import (
    TOOL_ARGUMENT_SCHEMAS,
    ApplyPatchArgs,
    ListRepositoryArgs,
    MAX_FILE_BYTES,
    MAX_PATCH_FILES,
    ReadFileArgs,
    RunValidationArgs,
    SearchRepositoryArgs,
    ToolCallRequest,
)


def test_every_registry_tool_has_an_argument_schema():
    assert set(TOOL_ARGUMENT_SCHEMAS) == set(TOOLS_BY_KEY)


def test_list_repository_rejects_unknown_field():
    with pytest.raises(ValidationError):
        ListRepositoryArgs(path="src", extra_field="nope")  # type: ignore[call-arg]


def test_read_file_requires_path():
    with pytest.raises(ValidationError):
        ReadFileArgs()  # type: ignore[call-arg]
    assert ReadFileArgs(path="a.py").path == "a.py"


def test_search_repository_requires_nonempty_pattern():
    with pytest.raises(ValidationError):
        SearchRepositoryArgs(pattern="")


def test_apply_patch_rejects_empty_file_list():
    with pytest.raises(ValidationError):
        ApplyPatchArgs(files=[])


def test_apply_patch_rejects_too_many_files():
    files = [{"path": f"f{i}.py", "content": "x"} for i in range(MAX_PATCH_FILES + 1)]
    with pytest.raises(ValidationError):
        ApplyPatchArgs(files=files)


def test_apply_patch_rejects_oversized_content():
    with pytest.raises(ValidationError):
        ApplyPatchArgs(files=[{"path": "a.py", "content": "a" * (MAX_FILE_BYTES + 1)}])


def test_apply_patch_accepts_optional_expected_content():
    parsed = ApplyPatchArgs(files=[{"path": "a.py", "content": "x", "expected_content": "old"}])
    assert parsed.files[0].expected_content == "old"
    parsed_none = ApplyPatchArgs(files=[{"path": "a.py", "content": "x"}])
    assert parsed_none.files[0].expected_content is None


def test_run_validation_requires_profile():
    with pytest.raises(ValidationError):
        RunValidationArgs()  # type: ignore[call-arg]
    assert RunValidationArgs(profile="pytest").profile == "pytest"


def test_tool_call_request_rejects_unknown_field():
    with pytest.raises(ValidationError):
        ToolCallRequest(
            tool_name="read_file",
            call_id="1",
            arguments={},
            unexpected="nope",  # type: ignore[call-arg]
        )


def test_tool_call_request_accepts_well_formed_call():
    call = ToolCallRequest(tool_name="read_file", call_id="1", arguments={"path": "a.py"})
    assert call.tool_name == "read_file"
