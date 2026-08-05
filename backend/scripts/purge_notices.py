"""Delete notices that have been off the board long enough to forget.

Expiry already *hides* a notice: every read path filters on `expires_at > now()`,
so nothing expired is ever served. This is the second half — actually removing
the rows, along with their stars and private replies (both CASCADE).

    cd backend
    .venv/bin/python scripts/purge_notices.py            # report only
    .venv/bin/python scripts/purge_notices.py --commit   # actually delete

Deliberately a script rather than a background task. There is no scheduler in
the deployment (Render's free tier has no cron), and a sweep that runs inside a
web request is a sweep that runs at an unpredictable moment under a user's
latency budget. Run it by hand, or point a scheduler at it when there is one.

GRACE_DAYS keeps a notice's row for a while after it leaves the board, so an
author who let something lapse can still be shown it under "Yours" and repost
it. Beyond that it's dead weight.
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select

from app.core.database import AsyncSessionLocal
from app.models import Notice

GRACE_DAYS = 30


async def main() -> None:
    commit = "--commit" in sys.argv
    cutoff = datetime.now(timezone.utc) - timedelta(days=GRACE_DAYS)

    async with AsyncSessionLocal() as session:
        doomed = (
            await session.scalar(
                select(func.count()).select_from(Notice).where(Notice.expires_at < cutoff)
            )
        ) or 0
        total = (
            await session.scalar(select(func.count()).select_from(Notice))
        ) or 0

        print(f"notices: {total} total")
        print(
            f"expired more than {GRACE_DAYS} days ago: {doomed} "
            f"(cutoff {cutoff.date().isoformat()})"
        )

        if not doomed:
            print("nothing to purge.")
            return
        if not commit:
            print("\ndry run — pass --commit to delete these.")
            return

        await session.execute(delete(Notice).where(Notice.expires_at < cutoff))
        await session.commit()
        print(f"purged {doomed} notices (stars and replies cascaded).")


if __name__ == "__main__":
    asyncio.run(main())
