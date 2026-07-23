"""Optionally seed the demo neighborhood on deploy — but only into an EMPTY
database.

Runs from the container's start command, after `alembic upgrade head` (which
guarantees the interests taxonomy exists). Behaviour:

  * SEED_DEMO not truthy  → no-op.
  * database already has events → no-op (so it never wipes real data, and only
    ever seeds on the very first boot).
  * otherwise → run the demo seed (scripts/seed_demo.py) with --force.

Enable it by setting the env var SEED_DEMO=true on the service, deploy once,
then it quietly does nothing on every deploy after.
"""

import asyncio
import os
import sys

from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.models import Event


def _enabled() -> bool:
    return os.getenv("SEED_DEMO", "").strip().lower() in {"1", "true", "yes", "on"}


async def _has_events() -> bool:
    async with AsyncSessionLocal() as session:
        return bool(await session.scalar(select(func.count()).select_from(Event)))


async def main() -> None:
    if not _enabled():
        print("seed_prod: SEED_DEMO not set — skipping.")
        return
    if await _has_events():
        print("seed_prod: database already has events — skipping.")
        return
    print("seed_prod: empty database + SEED_DEMO set — seeding demo data…")
    # seed_demo lives alongside this file; its own dir is on sys.path when run
    # as `python scripts/seed_prod.py`. It guards on a *_dev URL unless --force.
    sys.argv = [sys.argv[0], "--force"]
    import seed_demo

    await seed_demo.main()


if __name__ == "__main__":
    asyncio.run(main())
