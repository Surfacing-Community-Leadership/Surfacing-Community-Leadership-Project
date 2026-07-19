"""The Ticketmaster importer: normalizing, upserting, and map integration."""

from datetime import datetime, timedelta, timezone

from app.core.database import AsyncSessionLocal
from scripts.import_ticketmaster import cancel_missing, normalize_event, upsert_events

NEARBY = "/api/events?lat=40.6552&lng=-74.0069&radius_m=3000"


def tm_payload(**overrides):
    """A realistic Discovery API event near Sunset Park; override per test."""
    payload = {
        "id": "G5vYZ9AbCdEfG",
        "name": "Brooklyn Symphony: Summer Nights",
        "url": "https://www.ticketmaster.com/event/G5vYZ9AbCdEfG",
        "dates": {
            "start": {"dateTime": "2027-08-15T23:00:00Z"},
            "status": {"code": "onsale"},
        },
        "classifications": [
            {"segment": {"name": "Music"}, "genre": {"name": "Classical"}}
        ],
        "_embedded": {
            "venues": [
                {
                    "name": "Sunset Park Bandshell",
                    "location": {"latitude": "40.6558", "longitude": "-74.0072"},
                    "address": {"line1": "41st St & 5th Ave"},
                    "city": {"name": "Brooklyn"},
                }
            ]
        },
    }
    payload.update(overrides)
    return payload


def test_normalize_maps_all_fields():
    n = normalize_event(tm_payload())
    assert n["title"] == "Brooklyn Symphony: Summer Nights"
    assert n["kind"] == "gathering"
    assert (n["lat"], n["lng"]) == (40.6558, -74.0072)
    assert n["starts_at"] == datetime(2027, 8, 15, 23, 0, tzinfo=timezone.utc)
    assert n["external_ref"] == "ticketmaster/G5vYZ9AbCdEfG"
    assert n["external_url"].startswith("https://www.ticketmaster.com/")
    assert n["tag_slug"] == "music"  # Music segment -> our music interest
    assert "Sunset Park Bandshell" in n["address"]


def test_normalize_skips_unusable_entries():
    no_coords = tm_payload(_embedded={"venues": [{"name": "Somewhere"}]})
    assert normalize_event(no_coords) is None

    tba = tm_payload(dates={"start": {"localDate": "2027-08-15"}})
    assert normalize_event(tba) is None  # no concrete dateTime

    cancelled = tm_payload(
        dates={"start": {"dateTime": "2027-08-15T23:00:00Z"},
               "status": {"code": "cancelled"}}
    )
    assert normalize_event(cancelled) is None


def test_normalize_unmapped_segment_gets_no_tag():
    n = normalize_event(
        tm_payload(classifications=[{"segment": {"name": "Miscellaneous"}}])
    )
    assert n["tag_slug"] is None


async def test_upsert_is_idempotent_and_updates(make_user):
    first = normalize_event(tm_payload())
    renamed = normalize_event(tm_payload(name="Renamed at the source"))

    async with AsyncSessionLocal() as session:
        created, updated = await upsert_events(session, [first])
        assert (created, updated) == (1, 0)
        created, updated = await upsert_events(session, [renamed])
        assert (created, updated) == (0, 1)  # same external_ref -> update

    # One row, current title, discoverable on the map as an import.
    viewer = await make_user("viewer@example.com", "Viewer")
    found = [e for e in (await viewer.get(NEARBY)).json() if e["source"] == "imported"]
    assert len(found) == 1
    assert found[0]["title"] == "Renamed at the source"
    assert found[0]["tag_slug"] is None  # no interests seeded in this test DB


async def test_imported_event_shows_address_without_rsvp(make_user):
    async with AsyncSessionLocal() as session:
        await upsert_events(session, [normalize_event(tm_payload())])

    viewer = await make_user("viewer@example.com", "Viewer")
    listed = (await viewer.get(NEARBY)).json()
    event_id = next(e["id"] for e in listed if e["source"] == "imported")
    detail = (await viewer.get(f"/api/events/{event_id}")).json()
    # Not the host, no RSVP — but an imported venue is public information.
    assert detail["address"] and "Sunset Park Bandshell" in detail["address"]
    assert detail["external_url"].startswith("https://www.ticketmaster.com/")


async def test_cancel_missing_hides_events_gone_from_source(make_user):
    keep = normalize_event(tm_payload())
    gone = normalize_event(tm_payload(id="ZZgone999", name="Vanished show"))

    async with AsyncSessionLocal() as session:
        await upsert_events(session, [keep, gone])
        # A re-import inside the window that no longer returns "gone":
        window_end = datetime.now(timezone.utc) + timedelta(days=400)
        cancelled = await cancel_missing(session, {keep["external_ref"]}, window_end)
        assert cancelled == 1

    viewer = await make_user("viewer@example.com", "Viewer")
    titles = {e["title"] for e in (await viewer.get(NEARBY)).json()}
    assert "Brooklyn Symphony: Summer Nights" in titles
    assert "Vanished show" not in titles  # cancelled -> filtered off the map