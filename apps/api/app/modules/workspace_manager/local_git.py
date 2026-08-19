"""Local-filesystem git implementation of `WorkspaceManager`.

One real repo per company at `{workspace_root}/{project_id}`, driven
entirely through the plain `git` CLI (`git_process.git`). Pure I/O: no
EventBus, no knowledge of missions -- `workflow_engine` decides what
events to publish around these calls. Nothing in this module ever
executes, imports, or evaluates workspace content; content is only ever
written to disk, diffed, or read back as text.
"""

from __future__ import annotations

from pathlib import Path

from ...core.errors import WorkspaceConflictError
from ...core.interfaces.workspace_manager import (
    CommitResult,
    FileEntry,
    MergeRecord,
    WorkspaceManager,
    WriteResult,
)
from .git_process import GitCommandError, git
from .validation import MAX_FILES_PER_ATTEMPT, validate_content, validate_path

_README = """# Workspace

This repository is Commander's real, git-backed workspace for this
company. Employees commit here; the CEO reviews summaries and diffs in
the dashboard.
"""

_UNIT_SEP = "\x1f"


class LocalGitWorkspaceManager(WorkspaceManager):
    def __init__(self, workspace_root: str) -> None:
        self._root = Path(workspace_root).resolve()

    def _repo_dir(self, project_id: str) -> Path:
        return (self._root / project_id).resolve()

    def repo_root(self, project_id: str) -> Path:
        return self._repo_dir(project_id)

    async def ensure_initialized(self, project_id: str) -> bool:
        repo_dir = self._repo_dir(project_id)
        if (repo_dir / ".git").is_dir():
            return False
        repo_dir.mkdir(parents=True, exist_ok=True)
        await git(repo_dir, "init", "-q", "-b", "main")
        (repo_dir / "README.md").write_text(_README, encoding="utf-8")
        await git(repo_dir, "add", "README.md")
        await git(repo_dir, "commit", "-q", "-m", "Initial commit")
        return True

    async def create_branch(self, project_id: str, branch_name: str) -> None:
        repo_dir = self._repo_dir(project_id)
        exists = await git(
            repo_dir, "rev-parse", "--verify", "--quiet", branch_name, check=False
        )
        if exists.ok:
            return
        await git(repo_dir, "branch", branch_name, "main")

    async def write_files(
        self, project_id: str, branch_name: str, files: dict[str, str]
    ) -> WriteResult:
        repo_dir = self._repo_dir(project_id)
        await git(repo_dir, "checkout", "-q", branch_name)

        written: list[str] = []
        skipped: list[tuple[str, str]] = []
        to_add: list[str] = []

        for index, (path, content) in enumerate(files.items()):
            if index >= MAX_FILES_PER_ATTEMPT:
                skipped.append((path, f"exceeds {MAX_FILES_PER_ATTEMPT} files per attempt limit"))
                continue
            content_reason = validate_content(content)
            if content_reason is not None:
                skipped.append((path, content_reason))
                continue
            resolved, path_reason = validate_path(repo_dir, path)
            if resolved is None:
                skipped.append((path, path_reason or "invalid path"))
                continue
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content, encoding="utf-8")
            written.append(path)
            to_add.append(path)

        if to_add:
            await git(repo_dir, "add", "--", *to_add)

        return WriteResult(written=written, skipped=skipped)

    async def commit(
        self, project_id: str, branch_name: str, message: str
    ) -> CommitResult:
        repo_dir = self._repo_dir(project_id)
        await git(repo_dir, "checkout", "-q", branch_name)

        staged = await git(repo_dir, "diff", "--cached", "--quiet", check=False)
        if staged.ok:
            raise ValueError("commit() called with nothing staged")

        name_status = await git(repo_dir, "diff", "--cached", "--name-status")
        files_added = files_modified = files_deleted = 0
        for line in name_status.stdout.splitlines():
            if not line.strip():
                continue
            status = line.split("\t", 1)[0][:1]
            if status == "A":
                files_added += 1
            elif status == "D":
                files_deleted += 1
            else:
                files_modified += 1

        numstat = await git(repo_dir, "diff", "--cached", "--numstat")
        additions = deletions = 0
        for line in numstat.stdout.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            added, removed = parts[0], parts[1]
            additions += int(added) if added.isdigit() else 0
            deletions += int(removed) if removed.isdigit() else 0

        await git(repo_dir, "commit", "-q", "-m", message)
        sha = await git(repo_dir, "rev-parse", "HEAD")

        return CommitResult(
            commit_sha=sha.stdout.strip(),
            files_added=files_added,
            files_modified=files_modified,
            files_deleted=files_deleted,
            additions=additions,
            deletions=deletions,
        )

    async def diff(
        self, project_id: str, branch_name: str, *, max_chars: int = 12000
    ) -> tuple[str, bool]:
        repo_dir = self._repo_dir(project_id)
        result = await git(repo_dir, "diff", f"main...{branch_name}")
        text = result.stdout
        if len(text) > max_chars:
            return text[:max_chars], True
        return text, False

    async def diff_stats(self, project_id: str, branch_name: str) -> CommitResult:
        repo_dir = self._repo_dir(project_id)
        diff_range = f"main...{branch_name}"

        name_status = await git(repo_dir, "diff", diff_range, "--name-status")
        files_added = files_modified = files_deleted = 0
        for line in name_status.stdout.splitlines():
            if not line.strip():
                continue
            status = line.split("\t", 1)[0][:1]
            if status == "A":
                files_added += 1
            elif status == "D":
                files_deleted += 1
            else:
                files_modified += 1

        numstat = await git(repo_dir, "diff", diff_range, "--numstat")
        additions = deletions = 0
        for line in numstat.stdout.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            added, removed = parts[0], parts[1]
            additions += int(added) if added.isdigit() else 0
            deletions += int(removed) if removed.isdigit() else 0

        sha = await git(repo_dir, "rev-parse", branch_name)
        return CommitResult(
            commit_sha=sha.stdout.strip(),
            files_added=files_added,
            files_modified=files_modified,
            files_deleted=files_deleted,
            additions=additions,
            deletions=deletions,
        )

    async def merge(self, project_id: str, branch_name: str) -> str:
        repo_dir = self._repo_dir(project_id)
        await git(repo_dir, "checkout", "-q", "main")
        merged = await git(
            repo_dir,
            "merge",
            "--no-ff",
            "-q",
            "-m",
            f"Merge {branch_name}",
            branch_name,
            check=False,
        )
        if not merged.ok:
            await git(repo_dir, "merge", "--abort", check=False)
            raise WorkspaceConflictError(
                f"could not merge '{branch_name}' into main: {merged.stderr.strip()}"
            )
        sha = await git(repo_dir, "rev-parse", "HEAD")
        return sha.stdout.strip()

    async def head_sha(self, project_id: str, branch_name: str) -> str:
        repo_dir = self._repo_dir(project_id)
        result = await git(repo_dir, "rev-parse", branch_name)
        return result.stdout.strip()

    async def revert_last_commit(
        self, project_id: str, branch_name: str, target_sha: str
    ) -> None:
        repo_dir = self._repo_dir(project_id)
        await git(repo_dir, "checkout", "-q", branch_name)
        ancestry = await git(
            repo_dir, "merge-base", "--is-ancestor", target_sha, branch_name, check=False
        )
        if not ancestry.ok:
            raise WorkspaceConflictError(
                f"refusing to reset '{branch_name}' to {target_sha}: not an ancestor of its current HEAD"
            )
        await git(repo_dir, "reset", "--hard", target_sha)

    async def list_tree(self, project_id: str, ref: str = "main") -> list[FileEntry]:
        repo_dir = self._repo_dir(project_id)
        result = await git(repo_dir, "ls-tree", "-r", "--name-only", ref)
        return [FileEntry(path=line) for line in result.stdout.splitlines() if line.strip()]

    async def read_file(self, project_id: str, path: str, ref: str = "main") -> str:
        repo_dir = self._repo_dir(project_id)
        resolved, reason = validate_path(repo_dir, path)
        if resolved is None:
            raise ValueError(f"invalid path: {reason}")
        try:
            result = await git(repo_dir, "show", f"{ref}:{path}")
        except GitCommandError as exc:
            raise FileNotFoundError(f"{path} not found at {ref}") from exc
        return result.stdout

    async def recent_merges(
        self, project_id: str, limit: int = 10
    ) -> list[MergeRecord]:
        repo_dir = self._repo_dir(project_id)
        result = await git(
            repo_dir,
            "log",
            "main",
            "--merges",
            f"-n{limit}",
            f"--pretty=format:%H{_UNIT_SEP}%s{_UNIT_SEP}%aI",
            check=False,
        )
        records: list[MergeRecord] = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            parts = line.split(_UNIT_SEP)
            if len(parts) != 3:
                continue
            sha, subject, merged_at = parts
            records.append(MergeRecord(commit_sha=sha, subject=subject, merged_at=merged_at))
        return records
