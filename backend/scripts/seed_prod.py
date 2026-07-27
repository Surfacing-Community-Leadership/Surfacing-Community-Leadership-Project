"""Ensure the demo neighborhood is present on deploy.

Runs from the container start command, after `alembic upgrade head`. When
SEED_DEMO is truthy and the demo community ("Sunset Park") isn't in the
database yet, it runs the demo seed (scripts/seed_demo.py --force) to build it —
so the demo data shows up regardless of any stray rows already there.

Once the demo exists it's a no-op, so it won't wipe Ticketmaster-imported
events (or anything else) every time a free dyno wakes from sleep. Seeding
truncates users/events/communities, which is why it only runs while the demo
is absent. To force a fresh reseed, drop the demo community (or truncate) and
redeploy, or run `python scripts/seed_demo.py --force` from a shell.
"""

import asyncio
import os
import sys

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models import Community

DEMO_SLUG = "sunset-park"


def _enabled() -> bool:
    return os.getenv("SEED_DEMO", "").strip().lower() in {"1", "true", "yes", "on"}


async def _demo_present() -> bool:
    async with AsyncSessionLocal() as session:
        return bool(
            await session.scalar(select(Community.id).where(Community.slug == DEMO_SLUG))
        )


async def main() -> None:
    if not _enabled():
        print("seed_prod: SEED_DEMO not set — skipping.")
        return
    if await _demo_present():
        print("seed_prod: demo neighborhood already present — skipping.")
        return
    print("seed_prod: seeding the demo neighborhood…")
    # seed_demo lives alongside this file; its own dir is on sys.path when run
    # as `python scripts/seed_prod.py`. It guards on a *_dev URL unless --force.
    sys.argv = [sys.argv[0], "--force"]
    import seed_demo

    await seed_demo.main()


if __name__ == "__main__":
    asyncio.run(main())
