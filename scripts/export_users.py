"""Export all CEO accounts to CSV for an admin's own records.

Never includes a plaintext password -- only the bcrypt hash, which is
useless without the cost-12 compute to brute-force it. Writes to the path
given as the first argument, or stdout if omitted.

Run with the API's own venv: `apps/api/.venv/bin/python scripts/export_users.py [path]`
(or `make export-users`).
"""

from __future__ import annotations

import asyncio
import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "apps" / "api"
sys.path.insert(0, str(API_DIR))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db_models import UserORM  # noqa: E402

COLUMNS = ["id", "email", "display_name", "auth_provider", "created_at", "last_login_at", "password_hash"]


async def main() -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        result = await session.execute(select(UserORM).order_by(UserORM.created_at.asc()))
        users = list(result.scalars().all())

    await engine.dispose()

    out = sys.stdout if len(sys.argv) < 2 else open(sys.argv[1], "w", newline="", encoding="utf-8")
    try:
        writer = csv.writer(out)
        writer.writerow(COLUMNS)
        for user in users:
            writer.writerow(
                [
                    user.id,
                    user.email,
                    user.display_name,
                    user.auth_provider,
                    user.created_at.isoformat(),
                    user.last_login_at.isoformat() if user.last_login_at else "",
                    user.password_hash or "",
                ]
            )
    finally:
        if out is not sys.stdout:
            out.close()
            print(f"Exported {len(users)} user(s) to {sys.argv[1]}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
