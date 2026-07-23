"""Real provider: calls the Anthropic Messages API over httpx.

The API key is never read from env/config directly here — only through
SecretsProvider, so it's never logged and can be set at runtime from
Company Settings.
"""

from __future__ import annotations

from typing import Any

import httpx

from ...core.interfaces.provider_gateway import CompletionResult, ProviderGateway
from ...core.secrets import SecretsProvider

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider(ProviderGateway):
    def __init__(self, secrets: SecretsProvider) -> None:
        self._secrets = secrets

    async def complete(
        self,
        model_ref: str,
        system: str,
        messages: list[dict[str, str]],
        **opts: Any,
    ) -> CompletionResult:
        api_key = await self._secrets.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Anthropic provider selected but no ANTHROPIC_API_KEY is configured "
                "(set it in Company Settings or .env)."
            )

        max_tokens = opts.get("max_tokens", 1024)
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                ANTHROPIC_API_URL,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": ANTHROPIC_VERSION,
                    "content-type": "application/json",
                },
                json={
                    "model": model_ref,
                    "system": system,
                    "messages": messages,
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()
            data = response.json()

        text = "".join(block.get("text", "") for block in data.get("content", []))
        return CompletionResult(text=text, model=model_ref, provider="anthropic")
