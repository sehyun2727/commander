"""Real provider: calls the Anthropic Messages API over httpx.

The API key is never read from env/config directly here — only through
SecretsProvider, so it's never logged and can be set at runtime from
Company Settings.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from ...core.config import settings
from ...core.interfaces.provider_gateway import CompletionResult, ProviderGateway
from ...core.secrets import SecretsProvider

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider(ProviderGateway):
    def __init__(self, secrets: SecretsProvider) -> None:
        self._secrets = secrets

    async def _headers(self) -> dict[str, str]:
        api_key = await self._secrets.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Anthropic provider selected but no ANTHROPIC_API_KEY is configured "
                "(set it in Company Settings or .env)."
            )
        return {
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

    async def complete(
        self,
        model_ref: str,
        system: str,
        messages: list[dict[str, str]],
        **opts: Any,
    ) -> CompletionResult:
        headers = await self._headers()
        max_tokens = opts.get("max_tokens", 1024)
        async with httpx.AsyncClient(timeout=settings.provider_timeout_seconds) as client:
            response = await client.post(
                ANTHROPIC_API_URL,
                headers=headers,
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
        usage = data.get("usage", {})
        return CompletionResult(
            text=text,
            model=model_ref,
            provider="anthropic",
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )

    async def stream(
        self,
        model_ref: str,
        system: str,
        messages: list[dict[str, str]],
        usage: dict[str, int] | None = None,
        **opts: Any,
    ) -> AsyncIterator[str]:
        headers = await self._headers()
        max_tokens = opts.get("max_tokens", 1024)
        async with httpx.AsyncClient(timeout=settings.provider_timeout_seconds) as client:
            async with client.stream(
                "POST",
                ANTHROPIC_API_URL,
                headers=headers,
                json={
                    "model": model_ref,
                    "system": system,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    event = json.loads(line[len("data:"):].strip())
                    event_type = event.get("type")
                    if event_type == "content_block_delta":
                        text = event.get("delta", {}).get("text")
                        if text:
                            yield text
                    elif event_type == "message_start" and usage is not None:
                        msg_usage = event.get("message", {}).get("usage", {})
                        usage["input_tokens"] = msg_usage.get("input_tokens", 0)
                        usage.setdefault("output_tokens", 0)
                    elif event_type == "message_delta" and usage is not None:
                        usage["output_tokens"] = event.get("usage", {}).get(
                            "output_tokens", usage.get("output_tokens", 0)
                        )
