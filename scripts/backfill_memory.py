"""One-shot operator action: project pre-existing events into
`memory_records` for Companies that existed before the Sprint 18 memory
subscriber was installed. Safe to re-run -- `backfill_memory` is
idempotent (sprint-18.md Definition of Done #17).

Run with the API's own venv:
`apps/api/.venv/Scripts/python.exe scripts/backfill_memory.py [--project-id ID]`
Omitting --project-id backfills every Company.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "apps" / "api"

# Match the API's relative sqlite DB path convention (see scripts/seed.py).
os.chdir(API_DIR)
sys.path.insert(0, str(API_DIR))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.modules.event_bus import InProcessEventBus  # noqa: E402
from app.modules.memory import backfill_memory  # noqa: E402


async def main(project_id: str | None) -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    event_bus = InProcessEventBus(session_factory)

    count = await backfill_memory(session_factory, event_bus, project_id=project_id)
    scope = f"project {project_id}" if project_id else "all companies"
    print(f"Backfill complete for {scope}: {count} event(s) considered (duplicates skipped automatically).")

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill Project Memory from existing events.")
    parser.add_argument("--project-id", default=None, help="Limit backfill to one Company (default: all).")
    args = parser.parse_args()
    asyncio.run(main(args.project_id))
