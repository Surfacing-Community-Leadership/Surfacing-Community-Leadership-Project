"""Shared machinery for event importers (Ticketmaster, NYC Open Data, ICS…).

Every importer produces "normalized" dicts with the same keys:

    kind, title, description, lat, lng, address, starts_at, ends_at,
    external_ref, external_url, tag_slug

and then hands them to upsert_events(). external_ref is namespaced per source
("ticketmaster/<id>", "nyc/<id>/<date>", "ics/<feed>/<uid>") and unique in the
DB, so re-imports UPDATE their rows instead of duplicating, and
cancel_missing() can sweep one source's window without touching another's.
"""

from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core.geo import wkt_point
from app.models import Event, Interest


async def upsert_events(session, normalized: list[dict]) -> tuple[int, int]:
    """Insert new imported events / update existing ones by external_ref.
    Returns (created, updated)."""
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


async def cancel_missing(
    session,
    fetched_refs: set[str],
    window_end: datetime,
    ref_prefix: str,
    center: tuple[float, float] | None = None,
    radius_m: int | None = None,
) -> int:
    """Imported events this source no longer returns as upcoming were cancelled
    or removed at the source — mark them cancelled so the map's status filter
    hides them.

    The sweep may only cover what the fetch actually covered, or events the
    fetch legitimately couldn't know about get wrongly cancelled:
      - ref_prefix scopes to one source's rows;
      - window_end scopes to the fetched time horizon;
      - center+radius_m scope to the fetched AREA — essential for point-radius
        sources like Ticketmaster, where an import around one city must never
        sweep another city's rows.
    Callers whose fetch was TRUNCATED (hit a page/row cap) must not call this
    at all: an incomplete fetch can't tell "cancelled" from "beyond the cap"."""
    now = datetime.now(timezone.utc)
    stmt = select(Event).where(
        Event.source == "imported",
        Event.external_ref.startswith(ref_prefix),
        Event.starts_at > now,
        Event.starts_at < window_end,
        Event.status == "open",
    )
    if center is not None and radius_m is not None:
        point = func.ST_GeogFromText(wkt_point(center[0], center[1]))
        stmt = stmt.where(func.ST_DWithin(Event.location, point, radius_m))
    if fetched_refs:
        stmt = stmt.where(Event.external_ref.not_in(fetched_refs))
    stale = (await session.scalars(stmt)).all()
    for event in stale:
        event.status = "cancelled"
    await session.commit()
    return len(stale)
