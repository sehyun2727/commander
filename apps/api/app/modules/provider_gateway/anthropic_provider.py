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


def _legible_error(exc: httpx.HTTPStatusError) -> Exception:
    """Auth failures (401/403) are never transient — surface them as a
    plain-language RuntimeError a CEO can act on instead of the raw httpx
    message, which quotes the request URL and reads like an internal
    error. Everything else (429/5xx, which the gateway retries, and other
    4xx) is left as the original httpx error so `_is_retryable` and
    logging keep seeing the real exception."""
    status = exc.response.status_code
    if status in (401, 403):
        return RuntimeError(
            f"Anthropic rejected the configured API key (HTTP {status}). "
            "Check the key in Company Settings."
        )
    return exc


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
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise _legible_error(exc) from None
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
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raise _legible_error(exc) from None
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
