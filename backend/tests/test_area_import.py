"""Import-on-demand: tile claims, and the map-view-triggers-import flow."""

from datetime import datetime, timedelta, timezone

from app.core.area_import import claim_tile, tile_center, tile_key
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models import ImportArea
from tests.test_import import tm_payload

NEARBY = "/api/events?lat=40.6552&lng=-74.0069&radius_m=3000"


def test_tile_key_is_stable_within_a_tile_and_at_negatives():
    # Any point inside one tile maps to the same key…
    assert tile_key(40.6552, -74.0069) == tile_key(40.61, -74.24)
    # …and neighboring tiles differ.
    assert tile_key(40.6552, -74.0069) != tile_key(40.9, -74.0069)
    # Flooring is correct for negative coordinates (Sydney).
    assert tile_key(-33.87, 151.21) == "-34.00,151.00"
    lat, lng = tile_center(tile_key(40.6552, -74.0069))
    assert (lat, lng) == (40.625, -74.125)


async def test_claim_tile_single_winner_and_staleness():
    key = "40.50,-74.25"
    async with AsyncSessionLocal() as session:
        assert await claim_tile(session, key) is True     # first caller wins
        assert await claim_tile(session, key) is False    # running -> refused

        # Finished recently -> still fresh, refused.
        area = await session.get(ImportArea, key)
        area.status = "done"
        area.finished_at = datetime.now(timezone.utc)
        await session.commit()
        assert await claim_tile(session, key) is False

        # Finished long ago -> stale, reclaimable.
        area.finished_at = datetime.now(timezone.utc) - timedelta(hours=25)
        await session.commit()
        assert await claim_tile(session, key) is True


async def test_map_view_triggers_one_import(make_user, monkeypatch):
    """A cold map view imports its area in the background exactly once."""
    calls = []

    async def fake_fetch(lat, lng, radius_km, days):
        calls.append((round(lat, 3), round(lng, 3)))
        return [tm_payload()], True

    monkeypatch.setattr(
        "scripts.import_ticketmaster.fetch_events", fake_fetch
    )
    monkeypatch.setattr(settings, "ticketmaster_api_key", "test-key")

    viewer = await make_user("viewer@example.com", "Viewer")
    # First view: schedules the background import (runs before the transport
    # hands the response back in tests).
    first = (await viewer.get(NEARBY)).json()
    assert all(e["source"] != "imported" for e in first)  # ran after the query

    # Second view: the import has landed; the tile is fresh so NO new fetch.
    second = (await viewer.get(NEARBY)).json()
    imported = [e for e in second if e["source"] == "imported"]
    assert len(imported) == 1
    assert imported[0]["title"] == "Brooklyn Symphony: Summer Nights"
    assert len(calls) == 1  # two map views, exactly one Ticketmaster fetch
    # The fetch was centered on the tile, not the user's exact point.
    assert calls[0] == tile_center(tile_key(40.6552, -74.0069))


async def test_area_import_never_sweeps_other_cities(make_user, monkeypatch):
    """Regression: an import around one city must not cancel another city's
    rows. (This bug shipped briefly: a Chicago tile import cancelled ~900
    Brooklyn events because the sweep lacked geographic scope.)"""
    from scripts.import_common import upsert_events
    from scripts.import_ticketmaster import normalize_event

    chicago = normalize_event(
        tm_payload(id="CHI1", name="Chicago show",
                   _embedded={"venues": [{
                       "name": "Chicago Theatre",
                       "location": {"latitude": "41.8781", "longitude": "-87.6298"},
                   }]})
    )
    async with AsyncSessionLocal() as session:
        await upsert_events(session, [chicago])

    async def fake_fetch(lat, lng, radius_km, days):
        return [tm_payload()], True  # a COMPLETE Brooklyn fetch, no Chicago refs

    monkeypatch.setattr("scripts.import_ticketmaster.fetch_events", fake_fetch)
    monkeypatch.setattr(settings, "ticketmaster_api_key", "test-key")

    viewer = await make_user("viewer@example.com", "Viewer")
    await viewer.get(NEARBY)  # triggers the Brooklyn-tile import + sweep
    await viewer.get(NEARBY)  # ensure the background task has fully landed

    chi = (await viewer.get(
        "/api/events?lat=41.8781&lng=-87.6298&radius_m=3000"
    )).json()
    assert any(e["title"] == "Chicago show" for e in chi), (
        "Chicago row was swept by a Brooklyn-area import"
    )


async def test_truncated_fetch_skips_the_sweep(make_user, monkeypatch):
    """An import whose fetch hit the paging cap can't tell 'cancelled' from
    'beyond the cap' — it must not cancel anything."""
    from scripts.import_common import upsert_events
    from scripts.import_ticketmaster import normalize_event

    existing = normalize_event(tm_payload(id="OLD1", name="Previously imported"))
    async with AsyncSessionLocal() as session:
        await upsert_events(session, [existing])

    async def truncated_fetch(lat, lng, radius_km, days):
        return [tm_payload()], False  # same tile, but a TRUNCATED view

    monkeypatch.setattr("scripts.import_ticketmaster.fetch_events", truncated_fetch)
    monkeypatch.setattr(settings, "ticketmaster_api_key", "test-key")

    viewer = await make_user("viewer@example.com", "Viewer")
    await viewer.get(NEARBY)
    listed = (await viewer.get(NEARBY)).json()
    assert any(e["title"] == "Previously imported" for e in listed), (
        "a truncated fetch cancelled events it simply couldn't see"
    )


async def test_no_key_means_no_scheduling(make_user, monkeypatch):
    async def boom(*args, **kwargs):  # any fetch attempt is a failure
        raise AssertionError("fetch_events must not be called without a key")

    monkeypatch.setattr("scripts.import_ticketmaster.fetch_events", boom)
    # conftest forces the key empty; a map view must not claim any tile.
    viewer = await make_user("viewer@example.com", "Viewer")
    await viewer.get(NEARBY)
    async with AsyncSessionLocal() as session:
        assert await session.get(ImportArea, tile_key(40.6552, -74.0069)) is None