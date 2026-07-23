"""Port: the only path through which agents may call AI provider APIs.

Concrete implementations (MockProvider, AnthropicProvider) live in
modules/provider_gateway. Agent/workflow code depends only on this
interface, never on a specific provider SDK — swapping providers is a
model_registry + config change, not a code change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CompletionResult:
    text: str
    model: str
    provider: str


class ProviderGateway(ABC):
    @abstractmethod
    async def complete(
        self,
        model_ref: str,
        system: str,
        messages: list[dict[str, str]],
        **opts: Any,
    ) -> CompletionResult:
        """Send a system prompt + message history to the model behind
        `model_ref` (resolved via model_registry) and return its reply."""
