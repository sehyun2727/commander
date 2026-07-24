"""In-memory `SandboxRunner` for tests. Never shells out to Docker --
behavior is entirely controlled by the test, so orchestration logic
(Sprint 6 Phase 2's pipeline step) can be exercised without Docker being
installed, running, or even present in CI."""

from __future__ import annotations

from ...core.interfaces.sandbox import CheckResult, CheckStatus, SandboxCapability, SandboxRunner


class FakeSandbox(SandboxRunner):
    def __init__(
        self,
        *,
        available: bool = True,
        unavailable_reason: str | None = None,
        default_status: CheckStatus = "passed",
        results: dict[str, CheckResult] | None = None,
    ) -> None:
        self.available = available
        self.unavailable_reason = unavailable_reason
        self.default_status = default_status
        self._results = dict(results or {})
        self.calls: list[tuple[str, dict[str, str], list[str]]] = []

    async def capability(self) -> SandboxCapability:
        return SandboxCapability(available=self.available, reason=self.unavailable_reason)

    async def run_check(self, name: str, files: dict[str, str], command: list[str]) -> CheckResult:
        self.calls.append((name, files, command))
        if not self.available:
            return CheckResult(
                name=name, status="could_not_run", duration_seconds=0.0,
                output=self.unavailable_reason or "sandbox unavailable",
            )
        if name in self._results:
            canned = self._results[name]
            return CheckResult(
                name=name, status=canned.status, duration_seconds=canned.duration_seconds, output=canned.output
            )
        return CheckResult(
            name=name, status=self.default_status, duration_seconds=0.01,
            output="ok" if self.default_status == "passed" else "check failed",
        )
