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
    cors_origins: list[str] = ["http://localhost:3000"]
    provider_timeout_seconds: float = 60.0
    provider_max_retries: int = 2
    commander_workspace_root: str = "./workspaces"
    commander_sandbox_image: str = "commander-sandbox"
    # Narrative pacing (the 0.5-1.5s sleeps between pipeline beats) is a UX
    # device that makes the Timeline feel alive. Production keeps it on;
    # tests turn it off via conftest.py to avoid ~230s of pure sleep time.
    commander_pacing_enabled: bool = True
    # Mission budget guard (Rule #13) -- checked before each pipeline stage
    # starts; exceeding any one of these blocks the mission rather than
    # erroring, see modules/workflow_engine/engine.py._check_budget.
    commander_mission_max_tokens: int = 200_000
    commander_mission_max_usd: float = 5.0
    commander_mission_max_seconds: int = 900
    # Session cookie `secure` flag (Sprint 9 §2.1) -- local dev serves http,
    # so this stays False by default; a real deployment behind TLS must
    # override it, or the browser silently drops the cookie.
    commander_cookie_secure: bool = False
    commander_demo_email: str = "ceo@commander.local"
    commander_demo_password: str = "commander1234"
    # Agent Harness (Sprint 16, Rule #12/#13, DECISIONS.md #233) -- server
    # global policy switch and the tool-loop's own iteration/time budget,
    # checked in addition to (not instead of) the mission budget above;
    # exhaustion blocks the mission the same way
    # (modules/workflow_engine/engine.py._check_budget).
    commander_harness_enabled: bool = True
    commander_harness_max_tool_calls: int = 40
    commander_harness_max_seconds: int = 600
    commander_harness_max_output_bytes: int = 16 * 1024


settings = Settings()
