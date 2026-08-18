"""Structured tool-call argument schemas for the Agent Harness (Sprint 16
§4.2, DECISIONS.md #233).

Provider output is untrusted (CLAUDE.md §"Sprint 16 — Secure Agent
Harness"): a tool call is only ever accepted as a `tool_use` content block
with a known `tool_name` and JSON `arguments` that validate against the
matching schema below. There is no free-text command parsing anywhere in
this module -- `extra="forbid"` on every schema rejects any argument the
handler does not explicitly expect.

Bounds mirror `workspace_manager/validation.py`'s existing
`MAX_FILES_PER_ATTEMPT`/`MAX_FILE_BYTES` so a harness patch can never be
larger than what the one-shot Engineer path already allows.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

MAX_PATH_LENGTH = 4096
MAX_SEARCH_PATTERN_LENGTH = 256
MAX_SEARCH_RESULTS = 50
MAX_LIST_ENTRIES = 500
MAX_PATCH_FILES = 30  # mirrors workspace_manager.validation.MAX_FILES_PER_ATTEMPT
MAX_FILE_BYTES = 256 * 1024  # mirrors workspace_manager.validation.MAX_FILE_BYTES
MAX_PROFILE_NAME_LENGTH = 128


class ToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListRepositoryArgs(ToolArguments):
    path: str = Field(default="", max_length=MAX_PATH_LENGTH)


class ReadFileArgs(ToolArguments):
    path: str = Field(max_length=MAX_PATH_LENGTH)


class SearchRepositoryArgs(ToolArguments):
    pattern: str = Field(min_length=1, max_length=MAX_SEARCH_PATTERN_LENGTH)
    path: str = Field(default="", max_length=MAX_PATH_LENGTH)


class InspectGitArgs(ToolArguments):
    pass


class PatchFileEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(max_length=MAX_PATH_LENGTH)
    content: str = Field(max_length=MAX_FILE_BYTES)
    # Optional stale-write guard (DECISIONS.md #233): if supplied, apply_patch
    # rejects the whole patch when the file's current content differs from
    # this, rather than silently overwriting a change the Engineer never saw.
    expected_content: str | None = Field(default=None, max_length=MAX_FILE_BYTES)


class ApplyPatchArgs(ToolArguments):
    files: list[PatchFileEntry] = Field(min_length=1, max_length=MAX_PATCH_FILES)


class RunValidationArgs(ToolArguments):
    profile: str = Field(max_length=MAX_PROFILE_NAME_LENGTH)


TOOL_ARGUMENT_SCHEMAS: dict[str, type[ToolArguments]] = {
    "list_repository": ListRepositoryArgs,
    "read_file": ReadFileArgs,
    "search_repository": SearchRepositoryArgs,
    "inspect_git": InspectGitArgs,
    "apply_patch": ApplyPatchArgs,
    "run_validation": RunValidationArgs,
}


class ToolCallRequest(BaseModel):
    """One structured tool call, exactly as parsed from a provider's
    `tool_use` content block -- never free-text-parsed (Rule #9)."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str
    call_id: str
    arguments: dict
