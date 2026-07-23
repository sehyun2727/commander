from __future__ import annotations

import httpx
import pytest

from app.core.events import EventType
from app.core.interfaces.provider_gateway import CompletionResult, ProviderGateway
from app.modules.projects import service as projects_service
from app.modules.provider_gateway.gateway import RoutedProviderGateway


class FlakyProvider(ProviderGateway):
    """Test double: fails with a retryable/non-retryable error the first
    `fail_times` calls, then succeeds."""

    def __init__(self, fail_times: int, exc_factory=None) -> None:
        self.fail_times = fail_times
        self.calls = 0
        self._exc_factory = exc_factory or (lambda: httpx.ConnectError("boom"))

    async def complete(self, model_ref, system, messages, **opts) -> CompletionResult:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise self._exc_factory()
        return CompletionResult(text="ok", model=model_ref, provider="flaky")

    async def stream(self, model_ref, system, messages, usage=None, **opts):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise self._exc_factory()
        yield "ok"


def _http_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://example.test")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError("error", request=request, response=response)


@pytest.mark.asyncio
async def test_complete_retries_transient_failures_then_succeeds():
    flaky = FlakyProvider(fail_times=2)
    gateway = RoutedProviderGateway("mock", flaky, max_retries=2)
    result = await gateway.complete("planner-default", system="s", messages=[])
    assert result.text == "ok"
    assert flaky.calls == 3


@pytest.mark.asyncio
async def test_complete_gives_up_after_max_retries():
    flaky = FlakyProvider(fail_times=5)
    gateway = RoutedProviderGateway("mock", flaky, max_retries=2)
    with pytest.raises(httpx.ConnectError):
        await gateway.complete("planner-default", system="s", messages=[])
    assert flaky.calls == 3  # initial attempt + 2 retries


@pytest.mark.asyncio
async def test_non_retryable_status_is_not_retried():
    flaky = FlakyProvider(fail_times=1, exc_factory=lambda: _http_error(404))
    gateway = RoutedProviderGateway("mock", flaky, max_retries=2)
    with pytest.raises(httpx.HTTPStatusError):
        await gateway.complete("planner-default", system="s", messages=[])
    assert flaky.calls == 1


@pytest.mark.asyncio
async def test_retryable_status_5xx_is_retried():
    flaky = FlakyProvider(fail_times=1, exc_factory=lambda: _http_error(503))
    gateway = RoutedProviderGateway("mock", flaky, max_retries=2)
    result = await gateway.complete("planner-default", system="s", messages=[])
    assert result.text == "ok"
    assert flaky.calls == 2


@pytest.mark.asyncio
async def test_stream_retries_before_first_chunk_and_emits_retry_event(harness):
    project = await projects_service.create_project(
        harness.session_factory, harness.event_bus, harness.agent_runtime, name="Acme AI", provider="mock"
    )
    flaky = FlakyProvider(fail_times=1)
    gateway = RoutedProviderGateway(
        "mock", flaky, event_bus=harness.event_bus, project_id=project.id, max_retries=2
    )
    chunks = [chunk async for chunk in gateway.stream("planner-default", system="s", messages=[])]
    assert "".join(chunks) == "ok"
    assert flaky.calls == 2

    events = await harness.event_bus.recent(project.id, limit=50)
    retried = [e for e in events if e.type == EventType.PROVIDER_RETRIED]
    assert len(retried) == 1
    assert retried[0].payload["attempt"] == 1
