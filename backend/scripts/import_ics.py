"""Import events from any iCalendar (.ics) feed — libraries, churches,
community centers, mutual-aid groups. The most neighborly event data there is,
one hand-picked feed at a time.

Each feed gets an ANCHOR location (--lat/--lng): community calendars rarely
embed coordinates, but a feed usually belongs to a *place* (a library branch,
a community center), so every event lands on that pin unless the event itself
carries a GEO property. Run once per feed; cron a line per feed:

    cd backend
    .venv/bin/python -m scripts.import_ics \\
        --url https://example.org/calendar.ics \\
        --lat 40.6452 --lng -74.0104 \\
        --location-name "Sunset Park Library, 5108 4th Ave" \\
        --tag books-reading

--url also accepts a local file path (useful for testing a downloaded feed).
Recurring events (RRULE) are skipped for now and reported — expanding
recurrences is a follow-up. external_ref = "ics/<feed-hash>/<uid>" so each
feed's rows update in place and cancel-sync stays scoped to its own feed.
"""

import argparse
import asyncio
import hashlib
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from icalendar import Calendar

from app.core.database import AsyncSessionLocal
from scripts.import_common import cancel_missing, upsert_events

USER_AGENT = "OursApp/0.1 (neighborhood community MVP)"
LOCAL_TZ = ZoneInfo("America/New_York")  # assumed for floating/all-day times


def feed_prefix(url: str) -> str:
    """Stable per-feed ref namespace: ics/<8-char-hash-of-url>/"""
    return f"ics/{hashlib.sha256(url.encode()).hexdigest()[:8]}/"


def _to_utc(value) -> datetime:
    """DTSTART/DTEND values arrive as aware datetimes, naive datetimes
    (floating), or bare dates (all-day). Normalize all three to aware UTC."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=LOCAL_TZ)
        return value.astimezone(timezone.utc)
    # A bare date means "all day": midnight local.
    return datetime.combine(value, time.min, tzinfo=LOCAL_TZ).astimezone(timezone.utc)


def parse_feed(
    ics_text: str,
    url: str,
    anchor: tuple[float, float],
    location_name: str | None,
    tag_slug: str | None,
    window_start: datetime,
    window_end: datetime,
) -> tuple[list[dict], int]:
    """VEVENTs -> normalized dicts. Returns (events, skipped_recurring)."""
    calendar = Calendar.from_ical(ics_text)
    prefix = feed_prefix(url)
    events: list[dict] = []
    skipped_recurring = 0

    for component in calendar.walk("VEVENT"):
        if component.get("RRULE") is not None:
            skipped_recurring += 1
            continue
        dtstart = component.get("DTSTART")
        uid = component.get("UID")
        summary = component.get("SUMMARY")
        if dtstart is None or uid is None or summary is None:
            continue

        starts_at = _to_utc(dtstart.dt)
        if not (window_start <= starts_at <= window_end):
            continue

        ends_at = None
        dtend = component.get("DTEND")
        if dtend is not None:
            ends_at = _to_utc(dtend.dt)
            if isinstance(dtend.dt, date) and not isinstance(dtend.dt, datetime):
                # All-day DTEND is exclusive (the next day); pull it back so an
                # all-day event doesn't linger past midnight.
                ends_at -= timedelta(minutes=1)
            if ends_at <= starts_at:
                ends_at = None

        geo = component.get("GEO")
        lat, lng = (float(geo.latitude), float(geo.longitude)) if geo else anchor

        description = str(component.get("DESCRIPTION", "")).strip() or None
        event_url = str(component.get("URL", "")).strip() or None
        location_text = str(component.get("LOCATION", "")).strip()

        events.append(
            {
                "kind": "gathering",
                "title": str(summary)[:200],
                "description": description[:5000] if description else None,
                "lat": lat,
                "lng": lng,
                "address": location_text or location_name,
                "starts_at": starts_at,
                "ends_at": ends_at,
                "external_ref": f"{prefix}{uid}",
                "external_url": event_url or (url if url.startswith("http") else None),
                "tag_slug": tag_slug,
            }
        )
    return events, skipped_recurring


async def load_ics(url: str) -> str:
    if url.startswith(("http://", "https://")):
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": USER_AGENT})
            resp.raise_for_status()
            return resp.text
    return Path(url).read_text()


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help=".ics URL or local file path")
    parser.add_argument("--lat", type=float, required=True, help="anchor latitude")
    parser.add_argument("--lng", type=float, required=True, help="anchor longitude")
    parser.add_argument("--location-name", default=None,
                        help="address text for events without a LOCATION")
    parser.add_argument("--tag", default=None,
                        help="interest slug applied to the whole feed, e.g. books-reading")
    parser.add_argument("--days", type=int, default=60)
    args = parser.parse_args()

    print(f"Fetching {args.url} …")
    ics_text = await load_ics(args.url)

    now = datetime.now(timezone.utc)
    window_end = now + timedelta(days=args.days)
    events, skipped_recurring = parse_feed(
        ics_text, args.url, (args.lat, args.lng),
        args.location_name, args.tag, now, window_end,
    )

    async with AsyncSessionLocal() as session:
        created, updated = await upsert_events(session, events)
        cancelled = await cancel_missing(
            session, {e["external_ref"] for e in events}, window_end,
            ref_prefix=feed_prefix(args.url),
        )

    print(f"Done: {created} created, {updated} updated, {cancelled} marked "
          f"cancelled, {skipped_recurring} recurring events skipped (RRULE "
          f"expansion is a follow-up).")
    if not events:
        sys.exit("No events in the window — check the feed URL and --days.")


if __name__ == "__main__":
    asyncio.run(main())
