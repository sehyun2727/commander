"""App-wide settings, loaded from environment / .env via pydantic-settings.

Nothing outside `core.secrets` should read `Settings.anthropic_api_key`
directly — go through `SecretsProvider` so the key never gets logged and
can be overridden at runtime from Company Settings without an env change.
"""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    commander_provider: Literal["mock", "anthropic"] = "mock"
    anthropic_api_key: str | None = None
    # Postgres (via `make db-up` / docker-compose.yml) is the documented
    # default for `make dev`; sqlite+aiosqlite stays wired as the
    # zero-dependency fallback for tests and quick local runs (see
    # docs/DECISIONS.md Sprint 7).
    database_url: str = "postgresql+asyncpg://commander:commander@localhost:5432/commander"
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    provider_timeout_seconds: float = 60.0
    provider_max_retries: int = 2
    commander_workspace_root: str = "./workspaces"
    commander_sandbox_image: str = "commander-sandbox"


settings = Settings()
