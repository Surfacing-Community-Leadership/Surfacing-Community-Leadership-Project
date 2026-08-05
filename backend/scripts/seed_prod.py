"""Ensure the demo neighborhood is present, and current, on deploy.

Runs from the container start command, after `alembic upgrade head`.

Re-seeds when SEED_DEMO is truthy and either:
  * the demo community isn't there at all, or
  * it is there but was built by an older version of the seed.

That second case is the whole point of this file's existence. It used to check
only "does the Sunset Park community exist", which meant a database seeded once
never picked up anything added to the seed later — every feature that shipped
with demo data silently had none of it in production, and the deploy log
cheerfully said "already present — skipping".

The version lives in scripts/seed_demo.py as SEED_VERSION and is written to the
seed_state table at the end of a successful run. Bump it there when the seeded
content changes.

WHAT RE-SEEDING COSTS: seeding TRUNCATEs users, events, communities and
import_areas. Any account someone signed up for on the deployed app is deleted,
along with anything they made. That is the right trade for a demo deployment and
the wrong one for a real one — which is what SEED_DEMO is for. Set it to false
and this file does nothing at all.
"""

import asyncio
import os
import sys

from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.models import Community, SeedState, User

DEMO_SLUG = "sunset-park"


def _enabled() -> bool:
    return os.getenv("SEED_DEMO", "").strip().lower() in {"1", "true", "yes", "on"}


async def _state() -> tuple[bool, int | None, int]:
    """(demo community present, recorded seed version, live user count)."""
    async with AsyncSessionLocal() as session:
        present = bool(
            await session.scalar(select(Community.id).where(Community.slug == DEMO_SLUG))
        )
        version = await session.scalar(
            select(SeedState.version).order_by(SeedState.seeded_at.desc()).limit(1)
        )
        users = await session.scalar(select(func.count()).select_from(User)) or 0
    return present, version, users


async def main() -> None:
    if not _enabled():
        print("seed_prod: SEED_DEMO not set — skipping.")
        return

    # Imported here rather than at module scope so that turning SEED_DEMO off
    # can't be broken by an import error in the seed itself.
    sys.argv = [sys.argv[0], "--force"]
    import seed_demo

    wanted = seed_demo.SEED_VERSION
    present, found, users = await _state()

    if not present:
        reason = "demo neighborhood missing"
    elif found is None:
        # Seeded before versions existed, so it predates everything the marker
        # was introduced to catch.
        reason = f"demo present but unversioned (want v{wanted})"
    elif found < wanted:
        reason = f"demo is v{found}, want v{wanted}"
    elif found > wanted:
        # A rollback to an older image. Leave the newer data alone rather than
        # destroying it to install something older.
        print(
            f"seed_prod: database holds v{found}, newer than this build's "
            f"v{wanted} — leaving it alone."
        )
        return
    else:
        print(f"seed_prod: demo already at v{found} — skipping.")
        return

    print(f"seed_prod: re-seeding — {reason}.")
    print(f"seed_prod: this DELETES all {users} existing accounts and their data.")
    await seed_demo.main()


if __name__ == "__main__":
    asyncio.run(main())
