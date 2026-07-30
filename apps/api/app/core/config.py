"""App-wide settings, loaded from environment / .env via pydantic-settings.

Nothing outside `core.secrets` should read `Settings.anthropic_api_key`
directly — go through `SecretsProvider` so the key never gets logged and
can be overridden at runtime from Company Settings without an env change.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchored to the repo root (not the process cwd) so the single .env file
# next to docker-compose.yml is found the same way whether the API is
# launched from the repo root or from apps/api (as `make dev` does).
_REPO_ROOT_ENV = Path(__file__).resolve().parents[4] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_REPO_ROOT_ENV, env_prefix="", extra="ignore")

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
    # Narrative pacing (the 0.5-1.5s sleeps between pipeline beats) is a UX
    # device that makes the Timeline feel alive. Production keeps it on;
    # tests turn it off via conftest.py to avoid ~230s of pure sleep time.
    commander_pacing_enabled: bool = True


settings = Settings()
