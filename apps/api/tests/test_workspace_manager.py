from __future__ import annotations

import pytest

from app.core.errors import WorkspaceConflictError


@pytest.mark.asyncio
async def test_ensure_initialized_creates_repo_with_readme_on_main(harness):
    wm = harness.workspace_manager

    created = await wm.ensure_initialized("proj1")
    assert created is True

    tree = await wm.list_tree("proj1", ref="main")
    assert [f.path for f in tree] == ["README.md"]


@pytest.mark.asyncio
async def test_ensure_initialized_is_idempotent(harness):
    wm = harness.workspace_manager

    assert await wm.ensure_initialized("proj1") is True
    assert await wm.ensure_initialized("proj1") is False


@pytest.mark.asyncio
async def test_create_branch_is_idempotent(harness):
    wm = harness.workspace_manager
    await wm.ensure_initialized("proj1")

    await wm.create_branch("proj1", "mission/abc123")
    await wm.create_branch("proj1", "mission/abc123")  # no error


@pytest.mark.asyncio
async def test_write_files_skips_invalid_and_writes_valid(harness):
    wm = harness.workspace_manager
    await wm.ensure_initialized("proj1")
    await wm.create_branch("proj1", "mission/abc123")

    result = await wm.write_files(
        "proj1",
        "mission/abc123",
        {
            "src/app.py": "print('hello')\n",
            "../escape.py": "print('nope')\n",
            ".git/hooks/x": "nope",
        },
    )

    assert result.written == ["src/app.py"]
    skipped_paths = [path for path, _ in result.skipped]
    assert "../escape.py" in skipped_paths
    assert ".git/hooks/x" in skipped_paths


@pytest.mark.asyncio
async def test_write_files_then_commit_produces_stats(harness):
    wm = harness.workspace_manager
    await wm.ensure_initialized("proj1")
    await wm.create_branch("proj1", "mission/abc123")
    await wm.write_files(
        "proj1",
        "mission/abc123",
        {"src/app.py": "line1\nline2\nline3\n"},
    )

    result = await wm.commit("proj1", "mission/abc123", "Add app.py")

    assert result.files_added == 1
    assert result.files_modified == 0
    assert result.files_deleted == 0
    assert result.additions == 3
    assert result.deletions == 0
    assert len(result.commit_sha) == 40


@pytest.mark.asyncio
async def test_commit_with_nothing_staged_raises(harness):
    wm = harness.workspace_manager
    await wm.ensure_initialized("proj1")
    await wm.create_branch("proj1", "mission/abc123")

    with pytest.raises(ValueError):
        await wm.commit("proj1", "mission/abc123", "Nothing to commit")


@pytest.mark.asyncio
async def test_diff_shows_branch_changes_against_main(harness):
    wm = harness.workspace_manager
    await wm.ensure_initialized("proj1")
    await wm.create_branch("proj1", "mission/abc123")
    await wm.write_files("proj1", "mission/abc123", {"src/app.py": "print('hi')\n"})
    await wm.commit("proj1", "mission/abc123", "Add app.py")

    text, truncated = await wm.diff("proj1", "mission/abc123")

    assert "src/app.py" in text
    assert "print('hi')" in text
    assert truncated is False


@pytest.mark.asyncio
async def test_diff_truncates_when_over_max_chars(harness):
    wm = harness.workspace_manager
    await wm.ensure_initialized("proj1")
    await wm.create_branch("proj1", "mission/abc123")
    await wm.write_files("proj1", "mission/abc123", {"src/app.py": "x = 1\n" * 500})
    await wm.commit("proj1", "mission/abc123", "Add big file")

    text, truncated = await wm.diff("proj1", "mission/abc123", max_chars=100)

    assert len(text) == 100
    assert truncated is True


@pytest.mark.asyncio
async def test_merge_lands_branch_on_main(harness):
    wm = harness.workspace_manager
    await wm.ensure_initialized("proj1")
    await wm.create_branch("proj1", "mission/abc123")
    await wm.write_files("proj1", "mission/abc123", {"src/app.py": "print('hi')\n"})
    await wm.commit("proj1", "mission/abc123", "Add app.py")

    sha = await wm.merge("proj1", "mission/abc123")

    assert len(sha) == 40
    tree = await wm.list_tree("proj1", ref="main")
    assert "src/app.py" in [f.path for f in tree]
    content = await wm.read_file("proj1", "src/app.py", ref="main")
    assert content == "print('hi')\n"


@pytest.mark.asyncio
async def test_merge_conflict_raises_workspace_conflict_error(harness):
    wm = harness.workspace_manager
    await wm.ensure_initialized("proj1")

    await wm.create_branch("proj1", "mission/b1")
    await wm.write_files("proj1", "mission/b1", {"shared.txt": "from b1\n"})
    await wm.commit("proj1", "mission/b1", "b1 adds shared.txt")

    await wm.create_branch("proj1", "mission/b2")
    await wm.write_files("proj1", "mission/b2", {"shared.txt": "from b2\n"})
    await wm.commit("proj1", "mission/b2", "b2 adds shared.txt")

    await wm.merge("proj1", "mission/b1")

    with pytest.raises(WorkspaceConflictError):
        await wm.merge("proj1", "mission/b2")


@pytest.mark.asyncio
async def test_recent_merges_lists_merge_commits(harness):
    wm = harness.workspace_manager
    await wm.ensure_initialized("proj1")
    await wm.create_branch("proj1", "mission/abc123")
    await wm.write_files("proj1", "mission/abc123", {"src/app.py": "print('hi')\n"})
    await wm.commit("proj1", "mission/abc123", "Add app.py")
    sha = await wm.merge("proj1", "mission/abc123")

    merges = await wm.recent_merges("proj1")

    assert len(merges) == 1
    assert merges[0].commit_sha == sha
