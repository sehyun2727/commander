"""Fail-fast boot validation.

Runs once, at the top of main.py's lifespan, before any request is
served. Catches misconfiguration that would otherwise surface as a
confusing failure deep inside the first mission (a stray provider 401,
an opaque connection-refused traceback) and turns it into one
plain-language message a CEO -- not just a developer -- can act on.
Never runs during request handling.
"""

from __future__ import annotations

from .config import settings


class BootConfigError(RuntimeError):
    """Commander refuses to start with this configuration."""


def redact_database_url(database_url: str) -> str:
    """Drop user:pass@ from a DSN before it ever reaches a log line."""
    if "@" not in database_url:
        return database_url
    scheme_and_creds, host_and_rest = database_url.rsplit("@", 1)
    scheme = scheme_and_creds.split("://", 1)[0]
    return f"{scheme}://***@{host_and_rest}"


def validate_boot_config() -> None:
    if settings.commander_provider == "anthropic" and not settings.anthropic_api_key:
        raise BootConfigError(
            "COMMANDER_PROVIDER=anthropic but no ANTHROPIC_API_KEY is set. "
            "Set ANTHROPIC_API_KEY in .env (see .env.example), or switch "
            "COMMANDER_PROVIDER=mock to run without a key."
        )

    if not settings.database_url.startswith(("sqlite", "postgresql")):
        raise BootConfigError(
            f"DATABASE_URL ({redact_database_url(settings.database_url)}) is not a "
            "sqlite or postgresql URL. Commander only supports sqlite+aiosqlite "
            "(tests/local) or postgresql+asyncpg (via `make db-up`)."
        )

    # CORS runs with allow_credentials=True (main.py) so the session cookie
    # rides along with dashboard requests -- but browsers silently refuse to
    # send credentialed requests to a wildcard origin, so "*" here wouldn't
    # error, it would just quietly break login for everyone (Sprint 9 §2.1).
    if "*" in settings.cors_origins:
        raise BootConfigError(
            "CORS_ORIGINS contains a wildcard ('*'), which is incompatible with "
            "credentialed requests (session cookies never get sent). List the "
            "dashboard's real origin(s) instead, e.g. http://localhost:3000."
        )
