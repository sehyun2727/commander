"""Async wrapper around the `docker` CLI.

Mirrors `workspace_manager/git_process.py`'s shape: a thin, timeout-aware
subprocess wrapper with no knowledge of what's being run inside a
container. `DockerSandbox` is the only caller; everything here is plain
process I/O.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass(frozen=True)
class DockerResult:
    stdout: str
    stderr: str
    returncode: int

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class DockerUnavailableError(RuntimeError):
    """The `docker` binary could not be invoked at all (not installed, not on PATH)."""


class DockerTimedOutError(RuntimeError):
    """A docker invocation exceeded its timeout and was killed."""


async def docker(
    *args: str,
    input_bytes: bytes | None = None,
    timeout: float | None = None,
    merge_stderr: bool = False,
) -> DockerResult:
    """Run `docker <args>`, optionally piping `input_bytes` to stdin
    (used to stream a tar archive into a container via `docker cp -`).
    Raises DockerUnavailableError if the binary itself can't be found,
    DockerTimedOutError if `timeout` elapses (the process is killed, not
    left running). Never raises on a non-zero exit -- callers inspect
    `result.ok` themselves, since "docker command failed" is meaningful
    data (e.g. a failing check), not a Commander-level error. `merge_stderr`
    interleaves stderr into stdout (used for `docker start -a`, so a
    check's combined output reads the way it would in a terminal)."""
    try:
        process = await asyncio.create_subprocess_exec(
            "docker",
            *args,
            stdin=asyncio.subprocess.PIPE if input_bytes is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT if merge_stderr else asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise DockerUnavailableError("docker binary not found on PATH") from exc

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(input_bytes), timeout=timeout
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise DockerTimedOutError(f"docker {' '.join(args)} timed out after {timeout}s") from None

    return DockerResult(
        stdout=stdout_bytes.decode("utf-8", errors="replace"),
        stderr=(stderr_bytes or b"").decode("utf-8", errors="replace"),
        returncode=process.returncode or 0,
    )
