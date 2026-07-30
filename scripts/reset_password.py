"""Reset a CEO account's password from the command line.

There is no self-service "forgot password" flow this sprint (out of scope,
see CLAUDE.md V1.1 boundary) -- a locked-out CEO's only recourse is an
admin running this script against the server's own database.

Usage: `apps/api/.venv/bin/python scripts/reset_password.py --email <email> --password <new>`
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "apps" / "api"
sys.path.insert(0, str(API_DIR))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.modules.auth import service as auth_service  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    if len(args.password) < 8:
        print("FAIL: password must be at least 8 characters.", file=sys.stderr)
        return 1

    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    user = await auth_service.reset_password(session_factory, args.email, args.password)
    await engine.dispose()

    if user is None:
        print(f"FAIL: no account found for {args.email}", file=sys.stderr)
        return 1

    print(f"Password reset for {user.email}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
