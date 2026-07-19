"""Import-on-demand: the first map view of a cold area triggers a background
Ticketmaster import for it.

How it stays sane:
  - The world is a grid of TILE_DEG tiles. A map query stamps its tile.
  - Claiming a tile is one atomic upsert on import_areas (INSERT ... ON
    CONFLICT DO UPDATE ... WHERE stale). Exactly one request wins; everyone
    else's claim comes back empty and they do nothing. A 'done' tile goes
    stale after FRESH_FOR, a crashed 'running' one after STUCK_AFTER, a
    'failed' one retries after RETRY_AFTER.
  - The winner fetches ~20 km around the TILE center (not the user), so the
    coverage matches the tile stamp.
  - A small semaphore keeps concurrent imports from stampeding the API quota.

Net effect: a user opening the map in Chicago (or London — anywhere
Ticketmaster operates) gets that area imported once, in the background,
with no per-city setup. The map query itself is never delayed.
"""

import asyncio
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models import ImportArea

TILE_DEG = 0.25          # ~28 km of latitude per tile
IMPORT_RADIUS_KM = 20    # from tile center; covers the tile at city latitudes
IMPORT_DAYS = 30
FRESH_FOR = timedelta(hours=24)      # re-import a tile after this
STUCK_AFTER = timedelta(minutes=15)  # a 'running' claim older than this died
RETRY_AFTER = timedelta(hours=1)     # wait before retrying a 'failed' tile

# At most this many area imports at once, protecting the daily API quota from
# a burst of first-views across many cold tiles.
_import_slots = asyncio.Semaphore(2)


def tile_key(lat: float, lng: float) -> str:
    """The tile's SW corner, floored to the grid — stable for any point in it."""
    tlat = math.floor(lat / TILE_DEG) * TILE_DEG
    tlng = math.floor(lng / TILE_DEG) * TILE_DEG
    return f"{tlat:.2f},{tlng:.2f}"


def tile_center(key: str) -> tuple[float, float]:
    tlat, tlng = (float(part) for part in key.split(","))
    return tlat + TILE_DEG / 2, tlng + TILE_DEG / 2


async def claim_tile(session, key: str) -> bool:
    """Atomically claim a tile for importing. True only for the one caller
    that wins; a fresh/owned tile claims nothing."""
    now = datetime.now(timezone.utc)
    stmt = (
        pg_insert(ImportArea)
        .values(tile_key=key, status="running", started_at=now, finished_at=None)
        .on_conflict_do_update(
            index_elements=[ImportArea.tile_key],
            set_={"status": "running", "started_at": now, "finished_at": None},
            where=or_(
                and_(
                    ImportArea.status == "done",
                    ImportArea.finished_at < now - FRESH_FOR,
                ),
                and_(
                    ImportArea.status == "running",
                    ImportArea.started_at < now - STUCK_AFTER,
                ),
                and_(
                    ImportArea.status == "failed",
                    ImportArea.started_at < now - RETRY_AFTER,
                ),
            ),
        )
        .returning(ImportArea.tile_key)
    )
    won = (await session.execute(stmt)).first() is not None
    await session.commit()
    return won


async def _mark(session, key: str, status: str) -> None:
    area = await session.get(ImportArea, key)
    if area is not None:
        area.status = status
        area.finished_at = datetime.now(timezone.utc)
        await session.commit()


async def import_area(lat: float, lng: float) -> None:
    """The background task behind a map view: claim this point's tile and, if
    we won the claim, import events around the tile center. Never raises —
    a failed import must not take anything else down with it."""
    # Imported lazily: the scripts/ package is a sibling of app/ (importable
    # when running from backend/, as uvicorn and pytest both do) and pulls in
    # nothing heavy until an import actually runs.
    from scripts.import_common import cancel_missing, upsert_events
    from scripts.import_ticketmaster import fetch_events, normalize_event

    key = tile_key(lat, lng)
    async with AsyncSessionLocal() as session:
        if not await claim_tile(session, key):
            return
        try:
            async with _import_slots:
                center_lat, center_lng = tile_center(key)
                raw, complete = await fetch_events(
                    center_lat, center_lng, IMPORT_RADIUS_KM, IMPORT_DAYS
                )
                normalized = [n for n in map(normalize_event, raw) if n]
                await upsert_events(session, normalized)
                if complete:
                    # Sweep is scoped to THIS tile's fetch area — an import
                    # around one city must never cancel another city's rows.
                    # Skipped entirely on a truncated fetch, which can't tell
                    # "cancelled at source" from "beyond the paging cap".
                    await cancel_missing(
                        session,
                        {n["external_ref"] for n in normalized},
                        datetime.now(timezone.utc) + timedelta(days=IMPORT_DAYS),
                        ref_prefix="ticketmaster/",
                        center=(center_lat, center_lng),
                        radius_m=IMPORT_RADIUS_KM * 1000,
                    )
            await _mark(session, key, "done")
        except Exception as exc:  # noqa: BLE001 — background task, log and move on
            print(f"area import {key} failed: {exc!r}")
            await session.rollback()
            await _mark(session, key, "failed")


def maybe_schedule_area_import(background_tasks, lat: float, lng: float) -> None:
    """Called from the map query. Cheap no-op without an API key; otherwise
    schedules the claim-and-maybe-import to run after the response is sent."""
    if not settings.ticketmaster_api_key:
        return
    background_tasks.add_task(import_area, lat, lng)
