"""Fail-fast boot validation.

Runs once, at the top of main.py's lifespan, before any request is
served. Catches misconfiguration that would otherwise surface as a
confusing failure deep inside the first mission (a stray provider 401,
an opaque connection-refused traceback) and turns it into one
plain-language message a CEO -- not just a developer -- can act on.
Never runs during request handling.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .config import settings

_REPO_ROOT = Path(__file__).resolve().parents[4]
_ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


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

    if settings.commander_provider == "openrouter" and not settings.openrouter_api_key:
        raise BootConfigError(
            "COMMANDER_PROVIDER=openrouter but no OPENROUTER_API_KEY is set. "
            "Set OPENROUTER_API_KEY in .env (see .env.example), or switch "
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


def git_sha() -> str:
    """Best-effort short SHA for the boot log (Sprint 10 §0.3) -- 'unknown'
    outside a git checkout (e.g. a container built without .git) rather
    than failing boot over a diagnostic nicety."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=_REPO_ROOT,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


def alembic_head_revision() -> str | None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(Config(str(_ALEMBIC_INI)))
    return script.get_current_head()


async def _db_current_revision(engine) -> str | None:
    def _read(sync_conn):
        from alembic.runtime.migration import MigrationContext

        heads = MigrationContext.configure(sync_conn).get_current_heads()
        return heads[0] if heads else None

    async with engine.connect() as conn:
        return await conn.run_sync(_read)


async def validate_db_revision(engine, database_url: str) -> None:
    """Sprint 10 §0.3: print git SHA / Alembic head / current DB revision
    at boot, and refuse to serve traffic against a schema behind head.
    This is the diagnosability fix for Sprint 9's approval-500 incident,
    whose real cause was a stale API process on an old schema (see
    sprint10.md §4.1a) -- a mismatch here should be loud and immediate,
    not discovered later as a confusing runtime error on the first
    request that touches the missing column/table.

    SQLite is create_all-only (see core/db.py's init_db) and carries no
    Alembic history, so there is nothing to compare there -- only
    Postgres targets are checked.
    """
    if database_url.startswith("sqlite"):
        print("Commander booting: db=sqlite (create_all, no Alembic history)", file=sys.stderr)
        return

    head = alembic_head_revision()
    current = await _db_current_revision(engine)
    print(f"Commander booting: alembic_head={head} db_revision={current}", file=sys.stderr)
    if current != head:
        raise BootConfigError(
            f"Database schema is at revision {current!r} but the code expects "
            f"{head!r}. Run `make db-upgrade` (or `alembic upgrade head` from "
            "apps/api), then restart. If you just pulled new code, this is "
            "expected -- migrate before running it."
        )
