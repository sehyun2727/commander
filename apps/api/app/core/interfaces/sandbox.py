"""Port: isolated command execution for AI-generated code (Sprint 6).

This is the ONE place in Commander where AI-generated content is ever
executed, and it is deliberately narrow: `run_check` takes a trusted,
template-sourced `command` argv (never build one from model output) and a
`files` mapping that becomes the container's working directory. Nothing
here ever runs on the host -- a concrete implementation either executes
fully inside an isolated Docker container or refuses to run at all
(`capability().available is False`).

Sandbox trouble (no Docker, no image, daemon down, timeout, OOM) is never
an exception here -- it is a `CheckResult` with `status="could_not_run"`
so a flaky/absent sandbox can never crash a mission (see
docs/prompts/sprint-6.md, "Security model" #4).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

CheckStatus = Literal["passed", "failed", "could_not_run"]


@dataclass(frozen=True)
class SandboxCapability:
    """Whether execution is currently possible, and why not if not."""

    available: bool
    reason: str | None = None


@dataclass(frozen=True)
class CheckResult:
    """Outcome of one `run_check` call.

    `output` holds the tail-capped combined stdout+stderr when the check
    actually ran (`passed`/`failed`), or a plain-language explanation when
    it didn't (`could_not_run`) -- e.g. "Docker Desktop is not running",
    "sandbox image not found -- run `make sandbox-image`", "timed out
    after 120s", "container exceeded the memory limit".
    """

    name: str
    status: CheckStatus
    duration_seconds: float
    output: str


@dataclass(frozen=True)
class CheckSpec:
    """One template-defined check (Sprint 6 Phase 2): trusted, fixed
    `command` argv plus the glob(s) that decide whether it applies to a
    given mission's files. Lives next to `CheckResult`/`SandboxRunner`
    rather than in `templates/` because it's the sandbox port's input
    shape, not template-specific — `software_company` just supplies data
    of this shape."""

    name: str
    detect_globs: tuple[str, ...]
    command: tuple[str, ...]


class SandboxRunner(ABC):
    """Isolated, no-network command execution. Implementations own no
    knowledge of missions/checks -- the caller (workflow_engine, Sprint 6
    Phase 2) decides which commands to run and what to do with results."""

    @abstractmethod
    async def capability(self) -> SandboxCapability:
        """Probe whether execution is currently possible (Docker daemon
        reachable, sandbox image present). Cheap to call repeatedly --
        implementations should cache and re-probe on a short interval, not
        shell out on every call."""
        ...

    @abstractmethod
    async def run_check(self, name: str, files: dict[str, str], command: list[str]) -> CheckResult:
        """Run `command` inside a fresh, isolated container seeded with
        `files` as its working directory. `command` must come from trusted
        template data -- never interpolate AI-generated text into it.
        Always returns a CheckResult; never raises."""
        ...
