"""SecretsProvider: the only path to secret values (e.g. ANTHROPIC_API_KEY).

Wraps `.env` (via Settings) as the default, with a DB-backed override so the
CEO can paste a key into Company Settings without restarting the process.
Never log a value read from here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .config import settings
from .db_models import SettingORM

_ENV_DEFAULTS = {"ANTHROPIC_API_KEY": lambda: settings.anthropic_api_key}


class SecretsProvider(ABC):
    @abstractmethod
    async def get(self, name: str) -> str | None: ...

    @abstractmethod
    async def set(self, name: str, value: str) -> None: ...


class DBSecretsProvider(SecretsProvider):
    """DB override (`settings_kv` table) falling back to `.env`."""

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    async def get(self, name: str) -> str | None:
        async with self._session_factory() as session:
            row = await session.get(SettingORM, f"secret:{name}")
            if row is not None and row.value:
                return row.value
        default = _ENV_DEFAULTS.get(name)
        return default() if default else None

    async def set(self, name: str, value: str) -> None:
        async with self._session_factory() as session:
            row = await session.get(SettingORM, f"secret:{name}")
            if row is None:
                row = SettingORM(key=f"secret:{name}", value=value)
                session.add(row)
            else:
                row.value = value
            await session.commit()

    async def has(self, name: str) -> bool:
        return (await self.get(name)) is not None
