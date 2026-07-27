"""Async SQLAlchemy engine/session. `init_db()` applies Alembic migrations
against a real (Postgres) database on startup; SQLite stays on
`create_all` since it's only ever the ephemeral fallback for tests/quick
local runs, never a persistent target that needs migration history."""

from __future__ import annotations

import asyncio
from pathlib import Path
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import settings
from .db_models import Base

engine = create_async_engine(settings.database_url, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

_ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def upgrade_to_head() -> None:
    """Blocking; alembic's async env.py drives its own event loop
    internally (`asyncio.run(...)`), so callers on an existing loop
    (the FastAPI lifespan, seed.py) must run this via `asyncio.to_thread`
    rather than awaiting it directly."""
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(_ALEMBIC_INI)), "head")


async def init_db() -> None:
    if settings.database_url.startswith("sqlite"):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    else:
        await asyncio.to_thread(upgrade_to_head)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session
