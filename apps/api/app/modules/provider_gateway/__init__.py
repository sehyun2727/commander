"""Provider Gateway module.

Implements core.interfaces.provider_gateway.ProviderGateway. The only
module allowed to call AI provider APIs. `build_gateway` resolves the
active provider (mock by default, so Commander runs with no API key) and
routes logical model refs to concrete models via model_registry.
"""

from .anthropic_provider import AnthropicProvider
from .gateway import RoutedProviderGateway, build_gateway
from .mock_provider import MockProvider
from .openrouter_provider import OpenRouterProvider

__all__ = ["AnthropicProvider", "MockProvider", "OpenRouterProvider", "RoutedProviderGateway", "build_gateway"]
