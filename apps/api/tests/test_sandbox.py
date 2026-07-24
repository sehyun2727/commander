from __future__ import annotations

import asyncio
import shutil

import pytest

from app.core.interfaces.sandbox import CheckResult
from app.modules.sandbox.docker_sandbox import DockerSandbox
from app.modules.sandbox.docker_process import DockerResult, DockerTimedOutError, DockerUnavailableError
from app.modules.sandbox.fake_sandbox import FakeSandbox


def _docker_available() -> bool:
    """True only if the `docker` binary is on PATH *and* the daemon
    actually answers -- used to gate the real-Docker integration tests so
    they skip cleanly (not fail) on a machine with Docker installed but
    not running, or without Docker at all."""
    if shutil.which("docker") is None:
        return False

    async def _probe() -> bool:
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "info",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            returncode = await asyncio.wait_for(proc.wait(), timeout=5.0)
        except (OSError, asyncio.TimeoutError):
            return False
        return returncode == 0

    return asyncio.run(_probe())


DOCKER_AVAILABLE = _docker_available()


# ---------------------------------------------------------------------------
# FakeSandbox
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fake_sandbox_capability_available_by_default():
    sandbox = FakeSandbox()

    capability = await sandbox.capability()

    assert capability.available is True
    assert capability.reason is None


@pytest.mark.asyncio
async def test_fake_sandbox_capability_reports_configured_unavailable_reason():
    sandbox = FakeSandbox(available=False, unavailable_reason="Docker Desktop is not running")

    capability = await sandbox.capability()

    assert capability.available is False
    assert capability.reason == "Docker Desktop is not running"


@pytest.mark.asyncio
async def test_fake_sandbox_run_check_returns_could_not_run_when_unavailable():
    sandbox = FakeSandbox(available=False, unavailable_reason="no docker")

    result = await sandbox.run_check("pytest", {"test_x.py": "def test_x(): pass\n"}, ["pytest"])

    assert result.status == "could_not_run"
    assert result.output == "no docker"


@pytest.mark.asyncio
async def test_fake_sandbox_run_check_uses_default_status():
    sandbox = FakeSandbox(default_status="failed")

    result = await sandbox.run_check("pytest", {}, ["pytest"])

    assert result.status == "failed"
    assert result.output == "check failed"


@pytest.mark.asyncio
async def test_fake_sandbox_run_check_uses_canned_result_by_name():
    canned = CheckResult(name="pytest", status="failed", duration_seconds=1.23, output="1 failed, 0 passed")
    sandbox = FakeSandbox(results={"pytest": canned})

    result = await sandbox.run_check("pytest", {}, ["pytest"])

    assert result.status == "failed"
    assert result.duration_seconds == 1.23
    assert result.output == "1 failed, 0 passed"


@pytest.mark.asyncio
async def test_fake_sandbox_records_calls():
    sandbox = FakeSandbox()

    await sandbox.run_check("pytest", {"a.py": "x = 1\n"}, ["pytest", "-q"])

    assert sandbox.calls == [("pytest", {"a.py": "x = 1\n"}, ["pytest", "-q"])]


# ---------------------------------------------------------------------------
# DockerSandbox.capability() -- graceful unavailable paths, no real Docker
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_docker_sandbox_capability_unavailable_when_binary_missing(monkeypatch):
    sandbox = DockerSandbox()

    async def fake_docker(*args, **kwargs):
        raise DockerUnavailableError("docker binary not found on PATH")

    monkeypatch.setattr("app.modules.sandbox.docker_sandbox.docker", fake_docker)

    capability = await sandbox.capability()

    assert capability.available is False
    assert capability.reason == "Docker is not installed"


@pytest.mark.asyncio
async def test_docker_sandbox_capability_unavailable_when_daemon_times_out(monkeypatch):
    sandbox = DockerSandbox()

    async def fake_docker(*args, **kwargs):
        raise DockerTimedOutError("docker info timed out after 15.0s")

    monkeypatch.setattr("app.modules.sandbox.docker_sandbox.docker", fake_docker)

    capability = await sandbox.capability()

    assert capability.available is False
    assert capability.reason == "Docker Desktop is not responding"


@pytest.mark.asyncio
async def test_docker_sandbox_capability_unavailable_when_daemon_not_running(monkeypatch):
    sandbox = DockerSandbox()

    async def fake_docker(*args, **kwargs):
        return DockerResult(stdout="", stderr="Cannot connect to the Docker daemon", returncode=1)

    monkeypatch.setattr("app.modules.sandbox.docker_sandbox.docker", fake_docker)

    capability = await sandbox.capability()

    assert capability.available is False
    assert capability.reason == "Docker Desktop is not running"


@pytest.mark.asyncio
async def test_docker_sandbox_capability_unavailable_when_image_missing(monkeypatch):
    sandbox = DockerSandbox()

    async def fake_docker(*args, **kwargs):
        if args[0] == "info":
            return DockerResult(stdout="27.0.0", stderr="", returncode=0)
        return DockerResult(stdout="", stderr="No such image", returncode=1)

    monkeypatch.setattr("app.modules.sandbox.docker_sandbox.docker", fake_docker)

    capability = await sandbox.capability()

    assert capability.available is False
    assert "sandbox image not found" in capability.reason


@pytest.mark.asyncio
async def test_docker_sandbox_capability_available_when_daemon_and_image_ok(monkeypatch):
    sandbox = DockerSandbox()

    async def fake_docker(*args, **kwargs):
        return DockerResult(stdout="ok", stderr="", returncode=0)

    monkeypatch.setattr("app.modules.sandbox.docker_sandbox.docker", fake_docker)

    capability = await sandbox.capability()

    assert capability.available is True
    assert capability.reason is None


@pytest.mark.asyncio
async def test_docker_sandbox_capability_is_cached_within_ttl(monkeypatch):
    sandbox = DockerSandbox()
    call_count = 0

    async def fake_docker(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return DockerResult(stdout="ok", stderr="", returncode=0)

    monkeypatch.setattr("app.modules.sandbox.docker_sandbox.docker", fake_docker)

    await sandbox.capability()
    calls_after_first = call_count
    await sandbox.capability()

    assert call_count == calls_after_first  # second call served from cache, no new docker invocations


# ---------------------------------------------------------------------------
# DockerSandbox.run_check() -- could_not_run path when sandbox unavailable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_docker_sandbox_run_check_could_not_run_when_unavailable(monkeypatch):
    sandbox = DockerSandbox()

    async def fake_docker(*args, **kwargs):
        return DockerResult(stdout="", stderr="Cannot connect to the Docker daemon", returncode=1)

    monkeypatch.setattr("app.modules.sandbox.docker_sandbox.docker", fake_docker)

    result = await sandbox.run_check("pytest", {"test_x.py": "def test_x(): pass\n"}, ["pytest"])

    assert result.status == "could_not_run"
    assert result.output == "Docker Desktop is not running"
    assert result.name == "pytest"


@pytest.mark.asyncio
async def test_docker_sandbox_run_check_never_raises_on_unexpected_docker_error(monkeypatch):
    sandbox = DockerSandbox()

    async def fake_capability(self):
        from app.core.interfaces.sandbox import SandboxCapability

        return SandboxCapability(available=True)

    async def fake_docker(*args, **kwargs):
        raise DockerTimedOutError("docker create timed out after 15.0s")

    monkeypatch.setattr(DockerSandbox, "capability", fake_capability)
    monkeypatch.setattr("app.modules.sandbox.docker_sandbox.docker", fake_docker)

    result = await sandbox.run_check("pytest", {}, ["pytest"])

    assert result.status == "could_not_run"
    assert "timed out" in result.output


# ---------------------------------------------------------------------------
# Real-Docker integration tests -- skipped unless a working Docker daemon
# with the commander-sandbox image is actually reachable (never fail CI /
# a dev machine that just doesn't have Docker running).
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker daemon not reachable")
@pytest.mark.asyncio
async def test_real_docker_capability_available_with_image_built():
    sandbox = DockerSandbox()

    capability = await sandbox.capability()

    if not capability.available:
        pytest.skip(f"sandbox image not built: {capability.reason}")
    assert capability.available is True


@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker daemon not reachable")
@pytest.mark.asyncio
async def test_real_docker_run_check_passing_command():
    sandbox = DockerSandbox()
    capability = await sandbox.capability()
    if not capability.available:
        pytest.skip(f"sandbox image not built: {capability.reason}")

    result = await sandbox.run_check(
        "pytest",
        {"test_ok.py": "def test_ok():\n    assert 1 + 1 == 2\n"},
        ["python", "-m", "pytest", "-q"],
    )

    assert result.status == "passed"


@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker daemon not reachable")
@pytest.mark.asyncio
async def test_real_docker_run_check_failing_command():
    sandbox = DockerSandbox()
    capability = await sandbox.capability()
    if not capability.available:
        pytest.skip(f"sandbox image not built: {capability.reason}")

    result = await sandbox.run_check(
        "pytest",
        {"test_fail.py": "def test_fail():\n    assert 1 == 2\n"},
        ["python", "-m", "pytest", "-q"],
    )

    assert result.status == "failed"
    assert "1 == 2" in result.output or "failed" in result.output.lower()


@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker daemon not reachable")
@pytest.mark.asyncio
async def test_real_docker_run_check_has_no_network_access():
    sandbox = DockerSandbox()
    capability = await sandbox.capability()
    if not capability.available:
        pytest.skip(f"sandbox image not built: {capability.reason}")

    script = (
        "import socket\n"
        "def test_no_network():\n"
        "    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
        "    s.settimeout(3)\n"
        "    try:\n"
        "        s.connect(('8.8.8.8', 53))\n"
        "        raised = False\n"
        "    except OSError:\n"
        "        raised = True\n"
        "    assert raised, 'expected network access to be blocked'\n"
    )

    result = await sandbox.run_check(
        "pytest", {"test_net.py": script}, ["python", "-m", "pytest", "-q"]
    )

    assert result.status == "passed"
