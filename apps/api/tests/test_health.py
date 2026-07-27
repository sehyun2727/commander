from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import main


@pytest.mark.asyncio
async def test_health_is_always_ok():
    assert await main.health() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_db_returns_200_when_database_is_reachable(monkeypatch: pytest.MonkeyPatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(main, "async_session_factory", async_sessionmaker(engine, expire_on_commit=False))
    try:
        response = await main.health_db()
        assert response.status_code == 200
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_health_db_returns_503_without_a_traceback_when_unreachable(monkeypatch: pytest.MonkeyPatch):
    engine = create_async_engine("sqlite+aiosqlite:////nonexistent-dir-xyz/commander.db")
    monkeypatch.setattr(main, "async_session_factory", async_sessionmaker(engine, expire_on_commit=False))
    try:
        response = await main.health_db()
        assert response.status_code == 503
    finally:
        await engine.dispose()
