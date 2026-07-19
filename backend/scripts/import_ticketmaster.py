"""Import nearby public events from the Ticketmaster Discovery API.

Fills the map with real events that exist outside the app. Imported rows are
ordinary events with:

    source       = 'imported'   (schema anticipated this from day one)
    host_id      = NULL         (no host account; RSVP/messages still work)
    external_ref = 'ticketmaster/<id>'  (unique -> re-imports UPDATE, not duplicate)
    external_url = the event's Ticketmaster page

Usage (needs TICKETMASTER_API_KEY in backend/.env — free key from
developer.ticketmaster.com):

    cd backend
    .venv/bin/python -m scripts.import_ticketmaster                 # Sunset Park, 15 km, 30 days
    .venv/bin/python -m scripts.import_ticketmaster --lat 40.7 --lng -73.95 --radius-km 25 --days 60

Re-runnable: safe to cron. Events that Ticketmaster reports as cancelled are
flipped to status='cancelled', which our discovery filter already hides.
"""

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.geo import wkt_point
from app.models import Event, Interest

DISCOVERY_URL = "https://app.ticketmaster.com/discovery/v2/events.json"
USER_AGENT = "OursApp/0.1 (neighborhood community MVP)"
PAGE_SIZE = 100  # Discovery caps deep paging at page*size < 1000
MAX_PAGES = 9

# Ticketmaster classification segment -> our interest slug (best effort;
# anything unmapped just gets no tag and the default map icon).
SEGMENT_TO_SLUG = {
    "Music": "music",
    "Sports": "sports-fitness",
    "Arts & Theatre": "arts-crafts",
    "Film": "arts-crafts",
}


def normalize_event(item: dict) -> dict | None:
    """Turn one Discovery API event into kwargs for our Event model.
    Returns None for entries we can't place on the map (no coordinates),
    can't schedule (no concrete datetime), or that are already cancelled.
    Pure function so tests can feed it fixture payloads."""
    venues = (item.get("_embedded") or {}).get("venues") or [{}]
    venue = venues[0]
    loc = venue.get("location") or {}
    try:
        lat, lng = float(loc["latitude"]), float(loc["longitude"])
    except (KeyError, TypeError, ValueError):
        return None

    starts_raw = ((item.get("dates") or {}).get("start") or {}).get("dateTime")
    if not starts_raw:
        return None  # date-TBA events can't be placed on a time-filtered map
    starts_at = datetime.fromisoformat(starts_raw.replace("Z", "+00:00"))

    status_code = ((item.get("dates") or {}).get("status") or {}).get("code")
    if status_code == "cancelled":
        return None

    ends_raw = ((item.get("dates") or {}).get("end") or {}).get("dateTime")
    ends_at = (
        datetime.fromisoformat(ends_raw.replace("Z", "+00:00")) if ends_raw else None
    )

    address_bits = [
        venue.get("name"),
        (venue.get("address") or {}).get("line1"),
        ((venue.get("city") or {}).get("name")),
    ]
    address = ", ".join(bit for bit in address_bits if bit) or None

    classifications = item.get("classifications") or [{}]
    segment = ((classifications[0].get("segment") or {}).get("name"))
    genre = ((classifications[0].get("genre") or {}).get("name"))
    description_bits = [b for b in (segment, genre, venue.get("name")) if b]

    return {
        "kind": "gathering",
        "title": (item.get("name") or "Untitled event")[:200],
        "description": " · ".join(description_bits) or None,
        "lat": lat,
        "lng": lng,
        "address": address,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "external_ref": f"ticketmaster/{item['id']}",
        "external_url": item.get("url"),
        "tag_slug": SEGMENT_TO_SLUG.get(segment),
    }


async def fetch_events(lat: float, lng: float, radius_km: int, days: int) -> list[dict]:
    """Page through Discovery results around a point. Raises on HTTP errors —
    an import script should fail loudly, not half-succeed silently."""
    now = datetime.now(timezone.utc)
    params = {
        "apikey": settings.ticketmaster_api_key,
        "latlong": f"{lat},{lng}",
        "radius": max(1, round(radius_km)),
        "unit": "km",
        "size": PAGE_SIZE,
        "sort": "date,asc",
        # Discovery rejects fractional seconds; strip to whole seconds.
        "startDateTime": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endDateTime": (now + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    items: list[dict] = []
    async with httpx.AsyncClient(timeout=20.0) as client:
        for page in range(MAX_PAGES):
            resp = await client.get(
                DISCOVERY_URL,
                params={**params, "page": page},
                headers={"User-Agent": USER_AGENT},
            )
            resp.raise_for_status()
            data = resp.json()
            batch = (data.get("_embedded") or {}).get("events") or []
            items.extend(batch)
            total_pages = (data.get("page") or {}).get("totalPages", 1)
            if page + 1 >= total_pages:
                break
    return items


async def upsert_events(session, normalized: list[dict]) -> tuple[int, int]:
    """Insert new imported events / update existing ones by external_ref.
    Returns (created, updated). Importable so tests can drive it directly."""
    slugs = {n["tag_slug"] for n in normalized if n["tag_slug"]}
    tags_by_slug = {}
    if slugs:
        rows = (
            await session.scalars(select(Interest).where(Interest.slug.in_(slugs)))
        ).all()
        tags_by_slug = {t.slug: t.id for t in rows}

    created = updated = 0
    for n in normalized:
        values = {
            "kind": n["kind"],
            "title": n["title"],
            "description": n["description"],
            "location": wkt_point(n["lat"], n["lng"]),
            "address": n["address"],
            "starts_at": n["starts_at"],
            "ends_at": n["ends_at"],
            "visibility": "public",
            "source": "imported",
            "external_url": n["external_url"],
            "tag_id": tags_by_slug.get(n["tag_slug"]),
        }
        existing = await session.scalar(
            select(Event).where(Event.external_ref == n["external_ref"])
        )
        if existing is None:
            session.add(Event(external_ref=n["external_ref"], **values))
            created += 1
        else:
            for field, value in values.items():
                setattr(existing, field, value)
            updated += 1
    await session.commit()
    return created, updated


async def cancel_missing(session, fetched_refs: set[str], window_end: datetime) -> int:
    """Imported events that Ticketmaster no longer returns as upcoming were
    cancelled or removed at the source — mark them cancelled so the map's
    status filter hides them. Scoped to ticketmaster/ rows starting inside the
    window we actually fetched, so a narrower --days re-run can't wrongly
    cancel events beyond its horizon."""
    now = datetime.now(timezone.utc)
    stmt = select(Event).where(
        Event.source == "imported",
        Event.external_ref.startswith("ticketmaster/"),
        Event.starts_at > now,
        Event.starts_at < window_end,
        Event.status == "open",
    )
    if fetched_refs:
        stmt = stmt.where(Event.external_ref.not_in(fetched_refs))
    stale = (await session.scalars(stmt)).all()
    for event in stale:
        event.status = "cancelled"
    await session.commit()
    return len(stale)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lat", type=float, default=40.6552)
    parser.add_argument("--lng", type=float, default=-74.0069)
    parser.add_argument("--radius-km", type=int, default=15)
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()

    if not settings.ticketmaster_api_key:
        sys.exit(
            "TICKETMASTER_API_KEY is not set. Get a free key at "
            "developer.ticketmaster.com and add it to backend/.env"
        )

    print(f"Fetching events within {args.radius_km} km of "
          f"({args.lat}, {args.lng}) for the next {args.days} days…")
    raw = await fetch_events(args.lat, args.lng, args.radius_km, args.days)
    normalized = [n for n in (normalize_event(item) for item in raw) if n]
    skipped = len(raw) - len(normalized)

    window_end = datetime.now(timezone.utc) + timedelta(days=args.days)
    async with AsyncSessionLocal() as session:
        created, updated = await upsert_events(session, normalized)
        cancelled = await cancel_missing(
            session, {n["external_ref"] for n in normalized}, window_end
        )

    print(f"Done: {created} created, {updated} updated, {cancelled} marked "
          f"cancelled, {skipped} skipped (no coords/date or cancelled at source).")


if __name__ == "__main__":
    asyncio.run(main())
