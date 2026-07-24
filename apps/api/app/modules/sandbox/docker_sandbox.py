"""Docker implementation of `SandboxRunner` (Sprint 6).

One container per check, no reuse: create (stopped) -> stream a tar of
`files` in via `docker cp -` -> `docker start -a` under every mandatory
constraint -> capture -> `docker rm -f`. Never a bind mount (works
identically regardless of host filesystem/OneDrive quirks, and guarantees
the host can't be touched -- results only ever come back as captured
output). Every failure mode (no docker, no image, daemon down, timeout,
OOM) resolves to `CheckResult(status="could_not_run")`, never an
exception -- see `core/interfaces/sandbox.py`.
"""

from __future__ import annotations

import io
import tarfile
import time

from ...core.interfaces.sandbox import CheckResult, CheckStatus, SandboxCapability, SandboxRunner
from .docker_process import DockerTimedOutError, DockerUnavailableError, docker

DEFAULT_IMAGE = "commander-sandbox"

_SANDBOX_UID = 10001
_SANDBOX_GID = 10001
_MAX_OUTPUT_CHARS = 10_000
_HARD_TIMEOUT_SECONDS = 120.0
_COMMAND_TIMEOUT_SECONDS = 15.0
_CAPABILITY_CACHE_SECONDS = 5.0


def _tail(text: str, limit: int = _MAX_OUTPUT_CHARS) -> str:
    return text if len(text) <= limit else text[-limit:]


def _build_tar(files: dict[str, str]) -> bytes:
    """A tar stream with every entry pre-owned by the sandbox's non-root
    user, so files copied in via `docker cp -` are readable/writable by
    the user the container actually runs as (avoids the UID mismatch a
    bind mount or a naive `docker cp <host-dir>` would otherwise hit)."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        seen_dirs: set[str] = set()
        for path in files:
            parts = path.split("/")[:-1]
            prefix = ""
            for part in parts:
                prefix = f"{prefix}{part}/"
                dir_path = prefix.rstrip("/")
                if dir_path in seen_dirs:
                    continue
                seen_dirs.add(dir_path)
                info = tarfile.TarInfo(dir_path)
                info.type = tarfile.DIRTYPE
                info.mode = 0o755
                info.uid = _SANDBOX_UID
                info.gid = _SANDBOX_GID
                tar.addfile(info)
        for path, content in files.items():
            data = content.encode("utf-8")
            info = tarfile.TarInfo(path)
            info.size = len(data)
            info.mode = 0o644
            info.uid = _SANDBOX_UID
            info.gid = _SANDBOX_GID
            tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


class DockerSandbox(SandboxRunner):
    def __init__(self, image: str = DEFAULT_IMAGE) -> None:
        self._image = image
        self._cached: SandboxCapability | None = None
        self._cached_at: float = 0.0

    async def capability(self) -> SandboxCapability:
        now = time.monotonic()
        if self._cached is not None and (now - self._cached_at) < _CAPABILITY_CACHE_SECONDS:
            return self._cached
        result = await self._probe()
        self._cached = result
        self._cached_at = now
        return result

    async def _probe(self) -> SandboxCapability:
        try:
            info = await docker("info", "--format", "{{.ServerVersion}}", timeout=_COMMAND_TIMEOUT_SECONDS)
        except DockerUnavailableError:
            return SandboxCapability(available=False, reason="Docker is not installed")
        except DockerTimedOutError:
            return SandboxCapability(available=False, reason="Docker Desktop is not responding")
        if not info.ok:
            return SandboxCapability(available=False, reason="Docker Desktop is not running")

        try:
            image_check = await docker(
                "image", "inspect", self._image, timeout=_COMMAND_TIMEOUT_SECONDS
            )
        except (DockerUnavailableError, DockerTimedOutError):
            return SandboxCapability(available=False, reason="Docker Desktop is not responding")
        if not image_check.ok:
            return SandboxCapability(
                available=False, reason="sandbox image not found -- run `make sandbox-image`"
            )
        return SandboxCapability(available=True)

    async def run_check(self, name: str, files: dict[str, str], command: list[str]) -> CheckResult:
        capability = await self.capability()
        if not capability.available:
            return CheckResult(
                name=name, status="could_not_run", duration_seconds=0.0,
                output=capability.reason or "sandbox unavailable",
            )

        started = time.monotonic()
        container_id: str | None = None
        try:
            create = await docker(
                "create",
                "--network", "none",
                "--memory", "512m",
                "--cpus", "1",
                "--pids-limit", "256",
                "--user", f"{_SANDBOX_UID}:{_SANDBOX_GID}",
                "--workdir", "/workspace",
                self._image,
                *command,
                timeout=_COMMAND_TIMEOUT_SECONDS,
            )
            if not create.ok:
                return CheckResult(
                    name=name, status="could_not_run", duration_seconds=time.monotonic() - started,
                    output=f"could not create the sandbox container: {create.stderr.strip()[:500]}",
                )
            container_id = create.stdout.strip()

            copy = await docker(
                "cp", "-", f"{container_id}:/workspace",
                input_bytes=_build_tar(files), timeout=_COMMAND_TIMEOUT_SECONDS,
            )
            if not copy.ok:
                return CheckResult(
                    name=name, status="could_not_run", duration_seconds=time.monotonic() - started,
                    output=f"could not copy files into the sandbox: {copy.stderr.strip()[:500]}",
                )

            try:
                start = await docker(
                    "start", "-a", container_id, timeout=_HARD_TIMEOUT_SECONDS, merge_stderr=True
                )
            except DockerTimedOutError:
                await docker("kill", container_id, timeout=_COMMAND_TIMEOUT_SECONDS)
                return CheckResult(
                    name=name, status="could_not_run", duration_seconds=time.monotonic() - started,
                    output=f"timed out after {int(_HARD_TIMEOUT_SECONDS)}s",
                )

            duration = time.monotonic() - started
            oom = await docker(
                "inspect", "--format", "{{.State.OOMKilled}}", container_id,
                timeout=_COMMAND_TIMEOUT_SECONDS,
            )
            if oom.ok and oom.stdout.strip() == "true":
                return CheckResult(
                    name=name, status="could_not_run", duration_seconds=duration,
                    output="container exceeded the memory limit (OOM-killed)",
                )

            status: CheckStatus = "passed" if start.returncode == 0 else "failed"
            return CheckResult(name=name, status=status, duration_seconds=duration, output=_tail(start.stdout))
        except (DockerUnavailableError, DockerTimedOutError) as exc:
            return CheckResult(
                name=name, status="could_not_run", duration_seconds=time.monotonic() - started, output=str(exc)
            )
        finally:
            if container_id is not None:
                await docker("rm", "-f", container_id, timeout=_COMMAND_TIMEOUT_SECONDS)
