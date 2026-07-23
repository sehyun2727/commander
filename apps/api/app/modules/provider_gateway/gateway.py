"""The ProviderGateway the rest of the backend actually depends on.

Resolves a logical model ref ("planner-default") to the active provider's
concrete model id via model_registry, then delegates to that provider.
Callers never see a concrete model id or provider SDK — only this.
"""

from __future__ import annotations

from typing import Any

from ...core.interfaces.provider_gateway import CompletionResult, ProviderGateway
from ...core.secrets import SecretsProvider
from ..model_registry import resolve
from .anthropic_provider import AnthropicProvider
from .mock_provider import MockProvider


class RoutedProviderGateway(ProviderGateway):
    def __init__(self, provider_name: str, underlying: ProviderGateway) -> None:
        self.provider_name = provider_name
        self._underlying = underlying

    async def complete(
        self,
        model_ref: str,
        system: str,
        messages: list[dict[str, str]],
        **opts: Any,
    ) -> CompletionResult:
        concrete_model = resolve(self.provider_name, model_ref)
        return await self._underlying.complete(concrete_model, system, messages, **opts)


def build_gateway(provider_name: str, secrets: SecretsProvider) -> ProviderGateway:
    underlying: ProviderGateway = (
        MockProvider() if provider_name == "mock" else AnthropicProvider(secrets)
    )
    return RoutedProviderGateway(provider_name, underlying)
