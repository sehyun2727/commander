"""Async wrapper around the `git` CLI.

Every invocation pins a local, throwaway identity via `-c` flags rather
than touching global git config, since Commander may run in an
environment with no user.name/user.email configured (or one it shouldn't
overwrite). Nothing here ever executes workspace *content* — only `git`
itself, operating on it as opaque bytes.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

_GIT_IDENTITY = ["-c", "user.name=Commander", "-c", "user.email=commander@local"]


@dataclass(frozen=True)
class GitResult:
    stdout: str
    stderr: str
    returncode: int

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class GitCommandError(RuntimeError):
    """A git invocation exited non-zero and the caller required success."""

    def __init__(self, args: tuple[str, ...], result: GitResult) -> None:
        self.args = args
        self.result = result
        super().__init__(f"git {' '.join(args)} failed: {result.stderr.strip()}")


async def git(cwd: Path, *args: str, check: bool = True) -> GitResult:
    """Run `git <args>` in cwd. Raises GitCommandError if check and the
    process exits non-zero."""
    process = await asyncio.create_subprocess_exec(
        "git",
        *_GIT_IDENTITY,
        *args,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_bytes, stderr_bytes = await process.communicate()
    result = GitResult(
        stdout=stdout_bytes.decode("utf-8", errors="replace"),
        stderr=stderr_bytes.decode("utf-8", errors="replace"),
        returncode=process.returncode or 0,
    )
    if check and not result.ok:
        raise GitCommandError(args, result)
    return result
