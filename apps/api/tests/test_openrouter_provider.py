from __future__ import annotations

import json

import httpx
import pytest

from app.core.secrets import SecretsProvider
from app.modules.provider_gateway.openrouter_provider import OpenRouterProvider, _to_openai_messages, _to_openai_tools


class _FakeSecrets(SecretsProvider):
    def __init__(self, api_key: str | None) -> None:
        self._api_key = api_key

    async def get(self, name: str) -> str | None:
        return self._api_key if name == "OPENROUTER_API_KEY" else None

    async def set(self, name: str, value: str) -> None:
        self._api_key = value


def _mock_client(monkeypatch: pytest.MonkeyPatch, status: int, json_body: dict | None = None) -> None:
    """Patches httpx.AsyncClient so any request made through it returns a
    canned response, without hitting the real OpenRouter API."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=json_body or {})

    transport = httpx.MockTransport(handler)
    real_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)


@pytest.mark.asyncio
async def test_complete_raises_ceo_legible_error_on_401(monkeypatch: pytest.MonkeyPatch):
    _mock_client(monkeypatch, 401)
    provider = OpenRouterProvider(_FakeSecrets("bad-key"))
    with pytest.raises(RuntimeError) as exc_info:
        await provider.complete("some/model", system="s", messages=[{"role": "user", "content": "hi"}])
    message = str(exc_info.value)
    assert "Company Settings" in message
    assert "HTTP 401" in message


@pytest.mark.asyncio
async def test_complete_raises_ceo_legible_error_on_403(monkeypatch: pytest.MonkeyPatch):
    _mock_client(monkeypatch, 403)
    provider = OpenRouterProvider(_FakeSecrets("bad-key"))
    with pytest.raises(RuntimeError) as exc_info:
        await provider.complete("some/model", system="s", messages=[{"role": "user", "content": "hi"}])
    assert "Company Settings" in str(exc_info.value)


@pytest.mark.asyncio
async def test_complete_leaves_other_http_errors_as_httpx_errors(monkeypatch: pytest.MonkeyPatch):
    _mock_client(monkeypatch, 429)
    provider = OpenRouterProvider(_FakeSecrets("some-key"))
    with pytest.raises(httpx.HTTPStatusError):
        await provider.complete("some/model", system="s", messages=[{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_missing_api_key_raises_ceo_legible_error_without_a_request():
    provider = OpenRouterProvider(_FakeSecrets(None))
    with pytest.raises(RuntimeError) as exc_info:
        await provider.complete("some/model", system="s", messages=[])
    assert "no OPENROUTER_API_KEY is configured" in str(exc_info.value)


@pytest.mark.asyncio
async def test_complete_translates_text_response(monkeypatch: pytest.MonkeyPatch):
    _mock_client(
        monkeypatch,
        200,
        {
            "choices": [{"message": {"content": "hello there"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 4},
        },
    )
    provider = OpenRouterProvider(_FakeSecrets("some-key"))
    result = await provider.complete("some/model", system="s", messages=[{"role": "user", "content": "hi"}])
    assert result.text == "hello there"
    assert result.provider == "openrouter"
    assert result.input_tokens == 10
    assert result.output_tokens == 4
    assert result.stop_reason == "end_turn"
    assert result.tool_calls == ()


@pytest.mark.asyncio
async def test_complete_translates_tool_call_response(monkeypatch: pytest.MonkeyPatch):
    _mock_client(
        monkeypatch,
        200,
        {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {"name": "read_file", "arguments": '{"path": "a.py"}'},
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 20, "completion_tokens": 8},
        },
    )
    provider = OpenRouterProvider(_FakeSecrets("some-key"))
    result = await provider.complete(
        "some/model",
        system="s",
        messages=[{"role": "user", "content": "hi"}],
        tools=[{"name": "read_file", "description": "reads a file", "input_schema": {"type": "object"}}],
    )
    assert result.text == ""
    assert result.stop_reason == "tool_use"
    assert len(result.tool_calls) == 1
    call = result.tool_calls[0]
    assert call.call_id == "call_1"
    assert call.tool_name == "read_file"
    assert call.arguments == {"path": "a.py"}


@pytest.mark.asyncio
async def test_complete_tolerates_malformed_tool_call_arguments(monkeypatch: pytest.MonkeyPatch):
    _mock_client(
        monkeypatch,
        200,
        {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {"id": "call_1", "function": {"name": "read_file", "arguments": "not json"}}
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {},
        },
    )
    provider = OpenRouterProvider(_FakeSecrets("some-key"))
    result = await provider.complete("some/model", system="s", messages=[{"role": "user", "content": "hi"}])
    assert result.tool_calls[0].arguments == {}


def test_to_openai_tools_translates_anthropic_shape():
    tools = [{"name": "read_file", "description": "reads a file", "input_schema": {"type": "object", "properties": {}}}]
    translated = _to_openai_tools(tools)
    assert translated == [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "reads a file",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]


def test_to_openai_messages_prepends_system_and_passes_plain_strings():
    result = _to_openai_messages("be helpful", [{"role": "user", "content": "hi"}])
    assert result[0] == {"role": "system", "content": "be helpful"}
    assert result[1] == {"role": "user", "content": "hi"}


def test_to_openai_messages_translates_assistant_tool_use_block():
    messages = [
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "let me check"},
                {"type": "tool_use", "id": "call_1", "name": "read_file", "input": {"path": "a.py"}},
            ],
        }
    ]
    result = _to_openai_messages("s", messages)
    assistant = result[1]
    assert assistant["role"] == "assistant"
    assert assistant["content"] == "let me check"
    assert assistant["tool_calls"] == [
        {"id": "call_1", "type": "function", "function": {"name": "read_file", "arguments": json.dumps({"path": "a.py"})}}
    ]


def test_to_openai_messages_translates_user_tool_result_block():
    messages = [
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "call_1", "content": "file contents"}],
        }
    ]
    result = _to_openai_messages("s", messages)
    assert result[1] == {"role": "tool", "tool_call_id": "call_1", "content": "file contents"}


def test_to_openai_messages_marks_error_tool_result():
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "call_1", "content": "boom", "is_error": True}
            ],
        }
    ]
    result = _to_openai_messages("s", messages)
    assert result[1]["content"] == "[error] boom"


@pytest.mark.asyncio
async def test_stream_yields_text_deltas_and_updates_usage(monkeypatch: pytest.MonkeyPatch):
    body = (
        'data: {"choices": [{"delta": {"content": "Hel"}}]}\n\n'
        'data: {"choices": [{"delta": {"content": "lo"}}]}\n\n'
        'data: {"choices": [{"delta": {}}], "usage": {"prompt_tokens": 5, "completion_tokens": 2}}\n\n'
        "data: [DONE]\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body.encode(), headers={"content-type": "text/event-stream"})

    transport = httpx.MockTransport(handler)
    real_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

    provider = OpenRouterProvider(_FakeSecrets("some-key"))
    usage: dict[str, int] = {}
    chunks = []
    async for chunk in provider.stream("some/model", system="s", messages=[{"role": "user", "content": "hi"}], usage=usage):
        chunks.append(chunk)
    assert "".join(chunks) == "Hello"
    assert usage == {"input_tokens": 5, "output_tokens": 2}
