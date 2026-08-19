"""Sprint 19 §7.1: every HTTP request gets a server-issued correlation ID,
regardless of what a client sends -- trusting a client-supplied
`X-Request-Id` would let a forged header make unrelated requests appear
correlated in the logs."""

from __future__ import annotations

import uuid

import pytest

from app.core.logging import request_id_var


@pytest.mark.asyncio
async def test_response_carries_a_valid_uuid_request_id(api_client):
    response = await api_client.get("/api/health")
    request_id = response.headers["X-Request-Id"]
    assert uuid.UUID(request_id)


@pytest.mark.asyncio
async def test_middleware_ignores_client_supplied_request_id(api_client):
    response = await api_client.get("/api/health", headers={"X-Request-Id": "client-forged-id"})
    assert response.headers["X-Request-Id"] != "client-forged-id"
    assert uuid.UUID(response.headers["X-Request-Id"])


@pytest.mark.asyncio
async def test_each_request_gets_a_distinct_request_id(api_client):
    first = await api_client.get("/api/health")
    second = await api_client.get("/api/health")
    assert first.headers["X-Request-Id"] != second.headers["X-Request-Id"]


@pytest.mark.asyncio
async def test_request_id_var_is_reset_after_the_request_completes(api_client):
    assert request_id_var.get() is None
    await api_client.get("/api/health")
    assert request_id_var.get() is None
