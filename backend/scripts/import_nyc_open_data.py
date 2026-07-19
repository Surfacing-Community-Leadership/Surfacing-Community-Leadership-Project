"""Import public street/park events from NYC Open Data (permitted events).

Source: "NYC Permitted Event Information — Upcoming" (Socrata dataset
tvpp-9vvx). Free, no API key. This is the civic layer Ticketmaster can't see:
block parties, street festivals, farmers markets, parades — events that happen
on residential streets, which is exactly where the map looks empty.

The dataset gives text locations ("47 STREET between 5 AVENUE and 6 AVENUE"),
not coordinates, so we geocode at import time through Nominatim (same
User-Agent etiquette as the app's geocode proxy: 1 request/second, cached per
unique location within a run). Rows we can't geocode are counted and skipped.

Field permits (Sport - Youth/Adult) and film shoots are excluded — they're
private bookings, not invitations.

Usage:
    cd backend
    .venv/bin/python -m scripts.import_nyc_open_data                    # Brooklyn, 30 days
    .venv/bin/python -m scripts.import_nyc_open_data --borough Queens --days 60

Re-runnable: safe to cron. external_ref = "nyc/<event_id>/<date>" so multi-day
events keep one row per day and re-imports update in place.
"""

import argparse
import asyncio
import re
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx

from app.core.database import AsyncSessionLocal
from scripts.import_common import cancel_missing, upsert_events

DATASET_URL = "https://data.cityofnewyork.us/resource/tvpp-9vvx.json"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "OursApp/0.1 (neighborhood community MVP)"
NY_TZ = ZoneInfo("America/New_York")

# Public-facing permit types. Excluded on purpose: Sport - Youth / Sport -
# Adult (field rentals), Production Event / Theater Load in... (film shoots).
PUBLIC_EVENT_TYPES = (
    "Special Event",
    "Block Party",
    "Farmers Market",
    "Street Event",
    "Plaza Partner Event",
    "Open Street Partner Event",
    "Sidewalk Sale",
    "Parade",
    "Religious Event",
    "Plaza Event",
    "Athletic Race / Tour",
    "Health Fair",
    "Street Festival",
    "Single Block Festival",
    "Open Culture",
    "Clean-Up",
)

TYPE_TO_SLUG = {
    "Farmers Market": "cooking-food",
    "Health Fair": "health-wellness",
    "Athletic Race / Tour": "sports-fitness",
    "Clean-Up": "volunteering",
    "Parade": "local-history",
}

# Rough borough centroids + a radius that covers the borough, for scoping the
# cancelled-events sweep to the borough that was actually fetched.
BOROUGH_CENTERS = {
    "Brooklyn": (40.645, -73.945),
    "Manhattan": (40.776, -73.966),
    "Queens": (40.704, -73.828),
    "Bronx": (40.852, -73.866),
    "Staten Island": (40.581, -74.152),
}
BOROUGH_RADIUS_M = 20_000

# "DOUGLASS STREET between SMITH STREET and HOYT STREET"
BETWEEN_RE = re.compile(r"^(.*?)\s+between\s+(.*?)\s+and\s+(.*)$", re.IGNORECASE)

# Rows with these names are facility bookings that slipped through the type
# filter (e.g. Parks Department lawn reservations named "Miscellaneous") —
# a pin named "Miscellaneous" tells a neighbor nothing, so skip them.
JUNK_TITLES = {"miscellaneous", "misc", "tbd", "n/a", "private event"}


def _tidy(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def location_query(raw_location: str, borough: str) -> str:
    """Turn a permit location string into something Nominatim can resolve.
    Street segments become an intersection query (first cross street); park
    facilities ("Sunset Park: Soccer-01") become the park name."""
    loc = _tidy(raw_location)
    m = BETWEEN_RE.match(loc)
    if m:
        street, cross1, _ = (_tidy(part) for part in m.groups())
        return f"{street} & {cross1}, {borough}, New York"
    if ":" in loc:  # "Park Name: facility-code"
        loc = loc.split(":", 1)[0].strip()
    return f"{loc}, {borough}, New York"


def parse_row(row: dict) -> dict | None:
    """One dataset row -> normalized dict (minus lat/lng, which geocoding adds
    later via the 'location_query' key). None for rows we can't use."""
    starts_raw = row.get("start_date_time")
    name = row.get("event_name")
    location = row.get("event_location")
    if not (starts_raw and name and location and row.get("event_id")):
        return None
    if _tidy(name).lower() in JUNK_TITLES:
        return None

    # Socrata timestamps are floating local NY time ("2026-08-15T16:00:00.000").
    starts_local = datetime.fromisoformat(starts_raw).replace(tzinfo=NY_TZ)
    starts_at = starts_local.astimezone(timezone.utc)
    ends_at = None
    if row.get("end_date_time"):
        ends_local = datetime.fromisoformat(row["end_date_time"]).replace(tzinfo=NY_TZ)
        ends_at = ends_local.astimezone(timezone.utc)
        if ends_at <= starts_at:  # a few rows have inverted/zero ranges
            ends_at = None

    event_type = row.get("event_type", "")
    borough = row.get("event_borough", "New York")
    description_bits = [b for b in (event_type, row.get("event_agency")) if b]

    return {
        "kind": "gathering",
        "title": _tidy(name)[:200],
        "description": " · ".join(description_bits) or None,
        "address": f"{_tidy(location)}, {borough}",
        "starts_at": starts_at,
        "ends_at": ends_at,
        "external_ref": f"nyc/{row['event_id']}/{starts_local.date().isoformat()}",
        "external_url": None,  # the dataset has no per-event page
        "tag_slug": TYPE_TO_SLUG.get(event_type),
        "location_query": location_query(location, borough),
    }


async def fetch_rows(borough: str, days: int, limit: int) -> list[dict]:
    """Query Socrata for upcoming public-type events in one borough."""
    now_local = datetime.now(NY_TZ).replace(tzinfo=None)
    types = ", ".join(f"'{t}'" for t in PUBLIC_EVENT_TYPES)
    where = (
        f"event_borough='{borough}' AND event_type in({types}) "
        f"AND start_date_time > '{now_local.isoformat()}' "
        f"AND start_date_time < '{(now_local + timedelta(days=days)).isoformat()}'"
    )
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            DATASET_URL,
            params={"$where": where, "$order": "start_date_time", "$limit": limit},
            headers={"User-Agent": USER_AGENT},
        )
        resp.raise_for_status()
        return resp.json()


async def geocode_queries(queries: list[str]) -> dict[str, tuple[float, float]]:
    """Resolve unique location strings to (lat, lng) via Nominatim, one request
    per second per their usage policy. Returns only successful lookups."""
    results: dict[str, tuple[float, float]] = {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        for i, query in enumerate(queries):
            if i:
                await asyncio.sleep(1.1)  # etiquette: max ~1 req/s
            try:
                resp = await client.get(
                    NOMINATIM_URL,
                    params={"q": query, "format": "jsonv2", "limit": 1},
                    headers={"User-Agent": USER_AGENT},
                )
                resp.raise_for_status()
                data = resp.json()
            except (httpx.HTTPError, ValueError):
                continue
            if data:
                results[query] = (float(data[0]["lat"]), float(data[0]["lon"]))
    return results


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--borough", default="Brooklyn")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--limit", type=int, default=1000)
    args = parser.parse_args()

    print(f"Fetching {args.borough} permitted events for the next {args.days} days…")
    rows = await fetch_rows(args.borough, args.days, args.limit)
    # If we filled the row cap, the view is truncated: rows beyond the cap are
    # invisible to us, so "missing" must not be treated as "cancelled" below.
    complete = len(rows) < args.limit
    parsed = [p for p in (parse_row(row) for row in rows) if p]
    print(f"  {len(rows)} rows, {len(parsed)} usable")

    unique_queries = sorted({p["location_query"] for p in parsed})
    print(f"Geocoding {len(unique_queries)} unique locations "
          f"(~{len(unique_queries)} seconds, Nominatim rate limit)…")
    coords = await geocode_queries(unique_queries)

    normalized = []
    for p in parsed:
        hit = coords.get(p.pop("location_query"))
        if hit is None:
            continue
        p["lat"], p["lng"] = hit
        normalized.append(p)
    failed = len(parsed) - len(normalized)

    window_end = datetime.now(timezone.utc) + timedelta(days=args.days)
    async with AsyncSessionLocal() as session:
        created, updated = await upsert_events(session, normalized)
        cancelled = 0
        borough_center = BOROUGH_CENTERS.get(args.borough)
        if complete and borough_center is not None:
            # Scoped to this borough's area so a Brooklyn run can never sweep
            # a Queens run's rows.
            cancelled = await cancel_missing(
                session, {n["external_ref"] for n in normalized}, window_end,
                ref_prefix="nyc/",
                center=borough_center, radius_m=BOROUGH_RADIUS_M,
            )
        elif not complete:
            print("  row cap reached (truncated view) — skipping the "
                  "cancelled-events sweep for safety")

    print(f"Done: {created} created, {updated} updated, {cancelled} marked "
          f"cancelled, {failed} skipped (location not geocodable).")
    if failed and not normalized:
        sys.exit("Every location failed to geocode — check Nominatim access.")


if __name__ == "__main__":
    asyncio.run(main())
