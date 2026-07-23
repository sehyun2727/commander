"""The ProviderGateway the rest of the backend actually depends on.

Resolves a logical model ref ("planner-default") to the active provider's
concrete model id via model_registry, then delegates to that provider.
Callers never see a concrete model id or provider SDK — only this.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, AsyncIterator

import httpx

from ...core.events import Actor, EventType, build_event
from ...core.interfaces.event_bus import EventBus
from ...core.interfaces.provider_gateway import CompletionResult, ProviderGateway
from ...core.secrets import SecretsProvider
from ..model_registry import resolve
from .anthropic_provider import AnthropicProvider
from .mock_provider import MockProvider

logger = logging.getLogger("commander.provider_gateway")

SYSTEM_ACTOR = Actor(role="system", id="system", name="Commander")
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_STATUS
    return isinstance(exc, httpx.RequestError)


class RoutedProviderGateway(ProviderGateway):
    """Resolves logical model refs to concrete models, then wraps every
    call in retry-with-backoff for transient provider failures (429/5xx/
    network) — the resilience layer every call site gets for free,
    regardless of which concrete provider is behind it."""

    def __init__(
        self,
        provider_name: str,
        underlying: ProviderGateway,
        *,
        event_bus: EventBus | None = None,
        project_id: str | None = None,
        max_retries: int | None = None,
    ) -> None:
        self.provider_name = provider_name
        self._underlying = underlying
        self._event_bus = event_bus
        self._project_id = project_id
        if max_retries is None:
            from ...core.config import settings

            max_retries = settings.provider_max_retries
        self._max_retries = max_retries

    async def _publish_retry(self, attempt: int, reason: str) -> None:
        if not (self._event_bus and self._project_id):
            return
        await self._event_bus.publish(
            build_event(
                type=EventType.PROVIDER_RETRIED,
                project_id=self._project_id,
                actor=SYSTEM_ACTOR,
                payload={"provider": self.provider_name, "attempt": attempt},
                reason=reason,
            )
        )

    async def _backoff(self, attempt: int, exc: Exception) -> None:
        logger.warning("provider %s call failed (attempt %s): %s", self.provider_name, attempt, exc)
        await self._publish_retry(attempt, f"{type(exc).__name__}: {exc}")
        delay = 0.5 * (2 ** (attempt - 1)) + random.uniform(0, 0.25)
        await asyncio.sleep(delay)

    async def complete(
        self,
        model_ref: str,
        system: str,
        messages: list[dict[str, str]],
        **opts: Any,
    ) -> CompletionResult:
        concrete_model = resolve(self.provider_name, model_ref)
        attempt = 0
        while True:
            try:
                return await self._underlying.complete(concrete_model, system, messages, **opts)
            except Exception as exc:  # noqa: BLE001 - retry policy decides what's fatal
                if attempt >= self._max_retries or not _is_retryable(exc):
                    raise
                attempt += 1
                await self._backoff(attempt, exc)

    async def stream(
        self,
        model_ref: str,
        system: str,
        messages: list[dict[str, str]],
        usage: dict[str, int] | None = None,
        **opts: Any,
    ) -> AsyncIterator[str]:
        concrete_model = resolve(self.provider_name, model_ref)
        attempt = 0
        while True:
            yielded_any = False
            try:
                async for chunk in self._underlying.stream(
                    concrete_model, system, messages, usage=usage, **opts
                ):
                    yielded_any = True
                    yield chunk
                return
            except Exception as exc:  # noqa: BLE001 - retry policy decides what's fatal
                # A stream that already emitted text to the caller can't be
                # safely retried without duplicating output, so only retry
                # failures that happen before the first chunk (e.g. a 429
                # rejected before any SSE data arrives).
                if yielded_any or attempt >= self._max_retries or not _is_retryable(exc):
                    raise
                attempt += 1
                await self._backoff(attempt, exc)


def build_gateway(
    provider_name: str,
    secrets: SecretsProvider,
    *,
    event_bus: EventBus | None = None,
    project_id: str | None = None,
) -> ProviderGateway:
    underlying: ProviderGateway = (
        MockProvider() if provider_name == "mock" else AnthropicProvider(secrets)
    )
    return RoutedProviderGateway(provider_name, underlying, event_bus=event_bus, project_id=project_id)
