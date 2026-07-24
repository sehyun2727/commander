"""Port: the only path through which agents may call AI provider APIs.

Concrete implementations (MockProvider, AnthropicProvider) live in
modules/provider_gateway. Agent/workflow code depends only on this
interface, never on a specific provider SDK — swapping providers is a
model_registry + config change, not a code change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator


@dataclass(frozen=True)
class CompletionResult:
    text: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0


class ProviderGateway(ABC):
    async def resolve_model(self, model_ref: str, agent_override: str | None = None) -> str:
        """Resolve a logical ref ("planner-default") to the concrete model
        id that will actually serve the next call for it, honoring the
        three-tier override precedence (agent `profile.model_ref` > CEO
        per-role override > registry default). Exposed so callers
        (workflow_engine, tasks.service) can log the model actually used
        for cost accounting, rather than re-deriving it (and risking drift
        from an override) themselves.

        Concrete provider implementations (Mock/Anthropic) receive an
        already-resolved model id as `model_ref` from RoutedProviderGateway,
        so the identity default is correct for them; only the router
        overrides this with real logical-ref resolution."""
        return agent_override or model_ref

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

    @abstractmethod
    async def stream(
        self,
        model_ref: str,
        system: str,
        messages: list[dict[str, str]],
        usage: dict[str, int] | None = None,
        **opts: Any,
    ) -> AsyncIterator[str]:
        """Same call as `complete`, but yield the reply text incrementally.

        The return type is fixed to `AsyncIterator[str]`, and a single
        gateway instance may stream several missions concurrently, so
        there's nowhere on `self` to stash per-call usage. Instead, if the
        caller passes a plain `usage` dict, the provider mutates it in
        place with `input_tokens`/`output_tokens` once known (Anthropic's
        SSE protocol reports these mid-stream, before the text finishes)."""
        raise NotImplementedError
        yield ""  # pragma: no cover - makes this a generator function for subclasses
