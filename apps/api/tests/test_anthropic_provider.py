from __future__ import annotations

import httpx
import pytest

from app.core.secrets import SecretsProvider
from app.modules.provider_gateway.anthropic_provider import AnthropicProvider


class _FakeSecrets(SecretsProvider):
    def __init__(self, api_key: str | None) -> None:
        self._api_key = api_key

    async def get(self, name: str) -> str | None:
        return self._api_key if name == "ANTHROPIC_API_KEY" else None

    async def set(self, name: str, value: str) -> None:
        self._api_key = value


def _mock_client(monkeypatch: pytest.MonkeyPatch, status: int, json_body: dict | None = None) -> None:
    """Patches httpx.AsyncClient so any request made through it returns a
    canned response, without hitting the real Anthropic API."""

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
    provider = AnthropicProvider(_FakeSecrets("bad-key"))
    with pytest.raises(RuntimeError) as exc_info:
        await provider.complete("claude-x", system="s", messages=[{"role": "user", "content": "hi"}])
    message = str(exc_info.value)
    assert "Company Settings" in message
    assert "HTTP 401" in message


@pytest.mark.asyncio
async def test_complete_raises_ceo_legible_error_on_403(monkeypatch: pytest.MonkeyPatch):
    _mock_client(monkeypatch, 403)
    provider = AnthropicProvider(_FakeSecrets("bad-key"))
    with pytest.raises(RuntimeError) as exc_info:
        await provider.complete("claude-x", system="s", messages=[{"role": "user", "content": "hi"}])
    assert "Company Settings" in str(exc_info.value)


@pytest.mark.asyncio
async def test_complete_leaves_other_http_errors_as_httpx_errors(monkeypatch: pytest.MonkeyPatch):
    _mock_client(monkeypatch, 429)
    provider = AnthropicProvider(_FakeSecrets("some-key"))
    with pytest.raises(httpx.HTTPStatusError):
        await provider.complete("claude-x", system="s", messages=[{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_missing_api_key_raises_ceo_legible_error_without_a_request():
    provider = AnthropicProvider(_FakeSecrets(None))
    with pytest.raises(RuntimeError) as exc_info:
        await provider.complete("claude-x", system="s", messages=[])
    assert "no ANTHROPIC_API_KEY is configured" in str(exc_info.value)
