"""Real provider: calls OpenRouter's OpenAI-compatible chat-completions API.

OpenRouter routes to many upstream models (Claude, Llama, Qwen, Gemini,
free-tier community models, ...) but always speaks the OpenAI
`/v1/chat/completions` wire format, not Anthropic's `/v1/messages` -- so
this implements `ProviderGateway` directly rather than subclassing
`AnthropicProvider` (see docs/DECISIONS.md #249 / sprint-19.md §4.2).

The API key is never read from env/config directly here -- only through
SecretsProvider, matching AnthropicProvider's discipline.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from ...core.config import settings
from ...core.interfaces.provider_gateway import CompletionResult, ProviderGateway, ToolCallData
from ...core.secrets import SecretsProvider

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
# OpenRouter-recommended optional attribution headers -- deterministic,
# no client input (sprint-19.md §4.2).
_REFERER = "https://github.com/anthropics/commander"
_TITLE = "Commander"

_FINISH_REASON_MAP = {
    "stop": "end_turn",
    "tool_calls": "tool_use",
    "length": "max_tokens",
}


def _legible_error(exc: httpx.HTTPStatusError) -> Exception:
    """Mirrors AnthropicProvider._legible_error: auth failures are never
    transient, so surface a plain-language RuntimeError instead of the raw
    httpx message. Everything else (429/5xx, which the gateway retries,
    and other 4xx) is left as the original httpx error."""
    status = exc.response.status_code
    if status in (401, 403):
        return RuntimeError(
            f"OpenRouter rejected the configured API key (HTTP {status}). "
            "Check the key in Company Settings."
        )
    return exc


def _to_openai_messages(system: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Commander's (system, messages) -> OpenAI's messages list.

    Commander's `messages` may contain Anthropic-shaped content-block lists
    (assistant `tool_use` blocks, user `tool_result` blocks) when driven by
    the Agent Harness's tool loop (Sprint 16 §7) -- everywhere else,
    `content` is a plain string. Both shapes are translated here so the
    same tool loop works unmodified over OpenRouter."""
    out: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for message in messages:
        role = message["role"]
        content = message["content"]
        if isinstance(content, str):
            out.append({"role": role, "content": content})
            continue

        if role == "assistant":
            text_parts = [b.get("text", "") for b in content if b.get("type") == "text"]
            tool_calls = [
                {
                    "id": b["id"],
                    "type": "function",
                    "function": {"name": b["name"], "arguments": json.dumps(b.get("input") or {})},
                }
                for b in content
                if b.get("type") == "tool_use"
            ]
            assistant_msg: dict[str, Any] = {"role": "assistant", "content": "".join(text_parts) or None}
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            out.append(assistant_msg)
            continue

        # User-role tool_result blocks (one Anthropic user turn can carry
        # several) -> OpenAI's dedicated "tool" role, one message each.
        for block in content:
            if block.get("type") == "tool_result":
                text = block.get("content", "")
                if block.get("is_error"):
                    text = f"[error] {text}"
                out.append({"role": "tool", "tool_call_id": block["tool_use_id"], "content": text})
            else:
                out.append({"role": role, "content": block.get("text", "")})
    return out


def _to_openai_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Commander's tools=[{name, description, input_schema}] -> OpenAI's
    tools=[{"type": "function", "function": {name, description, parameters}}]."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {}),
            },
        }
        for tool in tools
    ]


def _tool_calls_from(message: dict[str, Any]) -> tuple[ToolCallData, ...]:
    calls: list[ToolCallData] = []
    for call in message.get("tool_calls") or []:
        function = call.get("function", {})
        raw_arguments = function.get("arguments") or "{}"
        try:
            arguments = json.loads(raw_arguments)
        except (TypeError, json.JSONDecodeError):
            arguments = {}
        calls.append(
            ToolCallData(call_id=call.get("id", ""), tool_name=function.get("name", ""), arguments=arguments)
        )
    return tuple(calls)


class OpenRouterProvider(ProviderGateway):
    def __init__(self, secrets: SecretsProvider) -> None:
        self._secrets = secrets

    async def _headers(self) -> dict[str, str]:
        api_key = await self._secrets.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OpenRouter provider selected but no OPENROUTER_API_KEY is configured "
                "(set it in Company Settings or .env)."
            )
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": _REFERER,
            "X-Title": _TITLE,
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
        payload: dict[str, Any] = {
            "model": model_ref,
            "messages": _to_openai_messages(system, messages),
            "max_tokens": max_tokens,
        }
        tools = opts.get("tools")
        if tools:
            payload["tools"] = _to_openai_tools(tools)
        async with httpx.AsyncClient(timeout=settings.provider_timeout_seconds) as client:
            response = await client.post(OPENROUTER_API_URL, headers=headers, json=payload)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise _legible_error(exc) from None
            data = response.json()

        choice = data["choices"][0]
        message = choice.get("message", {})
        usage = data.get("usage", {})
        finish_reason = choice.get("finish_reason") or "stop"
        return CompletionResult(
            text=message.get("content") or "",
            model=model_ref,
            provider="openrouter",
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            tool_calls=_tool_calls_from(message),
            stop_reason=_FINISH_REASON_MAP.get(finish_reason, finish_reason),
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
                OPENROUTER_API_URL,
                headers=headers,
                json={
                    "model": model_ref,
                    "messages": _to_openai_messages(system, messages),
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
                    raw = line[len("data:"):].strip()
                    if raw == "[DONE]":
                        break
                    event = json.loads(raw)
                    choices = event.get("choices") or []
                    delta = choices[0].get("delta", {}) if choices else {}
                    text = delta.get("content")
                    if text:
                        yield text
                    event_usage = event.get("usage")
                    if event_usage and usage is not None:
                        usage["input_tokens"] = event_usage.get("prompt_tokens", 0)
                        usage["output_tokens"] = event_usage.get("completion_tokens", 0)
