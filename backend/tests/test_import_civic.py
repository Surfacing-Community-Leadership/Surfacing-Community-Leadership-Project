"""The NYC Open Data and ICS importers: parsing, timezones, and scoping."""

from datetime import datetime, timedelta, timezone

from app.core.database import AsyncSessionLocal
from scripts.import_common import cancel_missing, upsert_events
from scripts.import_ics import feed_prefix, parse_feed
from scripts.import_nyc_open_data import location_query, parse_row

NEARBY = "/api/events?lat=40.6552&lng=-74.0069&radius_m=3000"


# --- NYC Open Data ---------------------------------------------------------

def nyc_row(**overrides):
    row = {
        "event_id": "735544",
        "event_name": "July Block Party",
        "start_date_time": "2027-07-24T12:00:00.000",
        "end_date_time": "2027-07-24T18:00:00.000",
        "event_agency": "Street Activity Permit Office",
        "event_type": "Block Party",
        "event_borough": "Brooklyn",
        "event_location": "47 STREET between 5 AVENUE and 6 AVENUE",
    }
    row.update(overrides)
    return row


def test_nyc_parse_row_converts_ny_time_to_utc():
    p = parse_row(nyc_row())
    # Noon Eastern (EDT, UTC-4) in July -> 16:00 UTC.
    assert p["starts_at"] == datetime(2027, 7, 24, 16, 0, tzinfo=timezone.utc)
    assert p["ends_at"] == datetime(2027, 7, 24, 22, 0, tzinfo=timezone.utc)
    assert p["title"] == "July Block Party"
    assert p["external_ref"] == "nyc/735544/2027-07-24"
    assert p["address"] == "47 STREET between 5 AVENUE and 6 AVENUE, Brooklyn"


def test_nyc_location_query_shapes():
    # Street segment -> intersection with the first cross street.
    assert (
        location_query("47 STREET between 5 AVENUE and 6 AVENUE", "Brooklyn")
        == "47 STREET & 5 AVENUE, Brooklyn, New York"
    )
    # Park facility -> just the park.
    assert (
        location_query("Sunset Park: Soccer-01", "Brooklyn")
        == "Sunset Park, Brooklyn, New York"
    )
    # Messy whitespace is tidied ("EAST   49 STREET" appears in real data).
    assert (
        location_query("EAST   49 STREET between AVENUE D and FOSTER AVENUE", "Brooklyn")
        == "EAST 49 STREET & AVENUE D, Brooklyn, New York"
    )


def test_nyc_parse_row_rejects_incomplete_and_inverted():
    assert parse_row(nyc_row(event_name=None)) is None
    assert parse_row(nyc_row(event_location=None)) is None
    # Inverted time range keeps the event but drops the bogus end.
    p = parse_row(nyc_row(end_date_time="2027-07-24T09:00:00.000"))
    assert p["ends_at"] is None


def test_nyc_junk_titles_skipped():
    # Parks facility bookings named "Miscellaneous" are reservations, not
    # invitations — they must not become map pins.
    assert parse_row(nyc_row(event_name="Miscellaneous")) is None
    assert parse_row(nyc_row(event_name="  MISC ")) is None


def test_nyc_tag_mapping():
    assert parse_row(nyc_row(event_type="Farmers Market"))["tag_slug"] == "cooking-food"
    assert parse_row(nyc_row(event_type="Block Party"))["tag_slug"] is None


# --- ICS feeds --------------------------------------------------------------

SAMPLE_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:storytime-42@example.org
SUMMARY:Toddler Storytime
DESCRIPTION:Songs and picture books.
LOCATION:Sunset Park Library
DTSTART:20270724T140000Z
DTEND:20270724T150000Z
URL:https://example.org/storytime
END:VEVENT
BEGIN:VEVENT
UID:allday-7@example.org
SUMMARY:Friends of the Library Book Sale
DTSTART;VALUE=DATE:20270725
DTEND;VALUE=DATE:20270726
END:VEVENT
BEGIN:VEVENT
UID:weekly-1@example.org
SUMMARY:Weekly Chess Club
DTSTART:20270701T220000Z
RRULE:FREQ=WEEKLY
END:VEVENT
BEGIN:VEVENT
UID:ancient-1@example.org
SUMMARY:Long-past event
DTSTART:20200101T120000Z
END:VEVENT
END:VCALENDAR
"""

ANCHOR = (40.6452, -74.0104)  # a library branch
WINDOW_START = datetime(2027, 7, 1, tzinfo=timezone.utc)
WINDOW_END = datetime(2027, 9, 1, tzinfo=timezone.utc)


def parse_sample():
    return parse_feed(
        SAMPLE_ICS, "https://example.org/cal.ics", ANCHOR,
        "Sunset Park Library, 5108 4th Ave", "books-reading",
        WINDOW_START, WINDOW_END,
    )


def test_ics_parses_timed_event_with_anchor_and_tag():
    events, skipped = parse_sample()
    story = next(e for e in events if "Storytime" in e["title"])
    assert story["starts_at"] == datetime(2027, 7, 24, 14, 0, tzinfo=timezone.utc)
    assert story["ends_at"] == datetime(2027, 7, 24, 15, 0, tzinfo=timezone.utc)
    assert (story["lat"], story["lng"]) == ANCHOR  # no GEO -> feed anchor
    assert story["address"] == "Sunset Park Library"  # LOCATION wins over default
    assert story["external_url"] == "https://example.org/storytime"
    assert story["tag_slug"] == "books-reading"
    assert story["external_ref"].startswith(feed_prefix("https://example.org/cal.ics"))


def test_ics_all_day_window_and_recurring():
    events, skipped_recurring = parse_sample()
    # Recurring and long-past events are excluded; timed + all-day survive.
    assert {e["title"] for e in events} == {
        "Toddler Storytime", "Friends of the Library Book Sale",
    }
    assert skipped_recurring == 1
    sale = next(e for e in events if "Book Sale" in e["title"])
    # All-day: starts midnight NY (04:00 UTC in July), exclusive DTEND pulled
    # back so it ends the same day.
    assert sale["starts_at"] == datetime(2027, 7, 25, 4, 0, tzinfo=timezone.utc)
    assert sale["ends_at"] < datetime(2027, 7, 26, 4, 0, tzinfo=timezone.utc)
    assert sale["address"] == "Sunset Park Library, 5108 4th Ave"  # default kicks in


# --- cross-source integration -----------------------------------------------

async def test_sources_upsert_and_cancel_independently(make_user):
    ics_events, _ = parse_sample()
    nyc_event = parse_row(nyc_row())
    nyc_event.pop("location_query")
    nyc_event["lat"], nyc_event["lng"] = 40.6549, -74.0061  # geocoded in real runs

    async with AsyncSessionLocal() as session:
        created, _ = await upsert_events(session, [*ics_events, nyc_event])
        assert created == 3
        # Sweeping the ICS feed's window must not touch nyc/ rows.
        cancelled = await cancel_missing(
            session, set(), datetime(2028, 1, 1, tzinfo=timezone.utc),
            ref_prefix=feed_prefix("https://example.org/cal.ics"),
        )
        assert cancelled == 2  # both ICS events, never the NYC one

    viewer = await make_user("viewer@example.com", "Viewer")
    titles = {e["title"] for e in (await viewer.get(NEARBY)).json()}
    assert "July Block Party" in titles          # NYC row still on the map
    assert "Toddler Storytime" not in titles     # ICS rows cancelled