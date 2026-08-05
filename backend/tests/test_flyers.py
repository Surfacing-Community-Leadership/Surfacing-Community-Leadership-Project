"""Flyer copy, and the one public view of an event.

The tests that matter most here are the negative ones. This feature adds the
only unauthenticated read of app data in the codebase, so most of what follows
is about what it must *not* return, and about the copy endpoint never failing in
a user's face when Gemini is unavailable.

No test hits the real Gemini API. GEMINI_API_KEY is unset in the test
environment (see conftest), so the templated path is what runs by default; the
model path is exercised by patching the module.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.core.flyer import (
    MAX_BLURB_CHARS,
    MAX_HEADLINE_CHARS,
    CopyOption,
    FlyerCopy,
    fallback_copy,
)
from tests.conftest import event_payload


async def _host_with_event(make_user, *, community=None, **overrides):
    """A logged-in host and one event they own.

    `community` joins them to a neighbourhood first, which the API requires
    before it will accept a community-only event.
    """
    host = await make_user("host@example.com", "Marcus")
    if community is not None:
        r = await host.patch("/api/profiles/me", json={"community_id": community})
        assert r.status_code == 200, r.text
    r = await host.post("/api/events", json=event_payload(**overrides))
    assert r.status_code == 201, r.text
    return host, r.json()["id"]


# ---- the copy endpoint -----------------------------------------------------


async def test_copy_falls_back_to_templated_when_gemini_is_unconfigured(make_user):
    """The whole reliability requirement in one test: no key, no error, still a
    usable flyer."""
    host, event_id = await _host_with_event(make_user)

    r = await host.post(f"/api/events/{event_id}/flyer-copy")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["generated"] is False
    assert len(body["options"]) >= 2
    for option in body["options"]:
        assert option["headline"] and option["blurb"]


async def test_templated_copy_does_not_spend_the_daily_allowance(make_user):
    """A Gemini outage must not eat everybody's quota on the way past."""
    host, event_id = await _host_with_event(make_user)

    first = (await host.post(f"/api/events/{event_id}/flyer-copy")).json()
    second = (await host.post(f"/api/events/{event_id}/flyer-copy")).json()
    assert first["remaining_today"] == first["daily_limit"]
    assert second["remaining_today"] == second["daily_limit"]


async def test_only_the_host_can_make_a_flyer(make_user):
    host, event_id = await _host_with_event(make_user)
    stranger = await make_user("stranger@example.com", "Ben")

    r = await stranger.post(f"/api/events/{event_id}/flyer-copy")
    assert r.status_code == 403
    assert "host" in r.json()["message"].lower()


async def test_a_private_event_cannot_have_a_flyer(make_user):
    """A flyer's QR points at a publicly readable page, so allowing one here
    would quietly undo the visibility the host chose."""
    host, event_id = await _host_with_event(make_user, visibility="private")

    r = await host.post(f"/api/events/{event_id}/flyer-copy")
    assert r.status_code == 409
    assert "private" in r.json()["message"].lower()


async def test_a_community_event_can_have_a_flyer(make_user, community_id):
    host, event_id = await _host_with_event(
        make_user, community=community_id, visibility="community"
    )
    r = await host.post(f"/api/events/{event_id}/flyer-copy")
    assert r.status_code == 200, r.text


async def test_the_daily_cap_is_enforced_and_survives_across_events(
    make_user, monkeypatch
):
    """The cap is per person per day, not per event — otherwise it would be
    trivially bypassed by making a second event."""
    monkeypatch.setattr(settings, "flyer_daily_limit", 2)
    host, first_event = await _host_with_event(make_user)
    r = await host.post("/api/events", json=event_payload(title="Another one"))
    second_event = r.json()["id"]

    # Force the model path so the calls actually count.
    async def fake_copy(**kwargs):
        return FlyerCopy(options=[CopyOption(headline="H", blurb="B")], generated=True)

    monkeypatch.setattr("app.routers.flyers.flyer_copy", fake_copy)

    a = await host.post(f"/api/events/{first_event}/flyer-copy")
    assert a.status_code == 200
    assert a.json()["remaining_today"] == 1

    b = await host.post(f"/api/events/{second_event}/flyer-copy")
    assert b.status_code == 200
    assert b.json()["remaining_today"] == 0

    # Third call, different event again — still refused.
    c = await host.post(f"/api/events/{first_event}/flyer-copy")
    assert c.status_code == 429
    assert "tomorrow" in c.json()["message"].lower()


async def test_a_model_failure_is_invisible_to_the_user(make_user, monkeypatch):
    """A timeout, a quota error or a malformed reply all land on the same
    behaviour: templated copy and a 200."""
    host, event_id = await _host_with_event(make_user)

    monkeypatch.setattr(settings, "gemini_api_key", "test-key-not-real")

    class Boom(Exception):
        pass

    def explode(*args, **kwargs):
        raise Boom("simulated quota exhaustion")

    # Patched at the import site inside flyer_copy.
    monkeypatch.setattr("google.genai.Client", explode, raising=False)

    r = await host.post(f"/api/events/{event_id}/flyer-copy")
    assert r.status_code == 200, r.text
    assert r.json()["generated"] is False
    assert r.json()["options"]


async def test_generated_copy_is_reported_and_counted(make_user, monkeypatch):
    host, event_id = await _host_with_event(make_user)

    async def fake_copy(**kwargs):
        return FlyerCopy(
            options=[CopyOption(headline="Come to the park", blurb="Bring a blanket.")],
            generated=True,
        )

    monkeypatch.setattr("app.routers.flyers.flyer_copy", fake_copy)

    r = await host.post(f"/api/events/{event_id}/flyer-copy")
    body = r.json()
    assert body["generated"] is True
    assert body["options"][0]["headline"] == "Come to the park"
    assert body["remaining_today"] == body["daily_limit"] - 1


async def test_flyer_copy_needs_a_login(client):
    r = await client.post(f"/api/events/{'0' * 8}-0000-0000-0000-{'0' * 12}/flyer-copy")
    assert r.status_code == 401


# ---- the public page behind the QR code ------------------------------------


async def test_the_public_page_needs_no_login(client, make_user):
    """`client` carries no cookies at all — this is the scanned-a-flyer path."""
    _, event_id = await _host_with_event(make_user)

    r = await client.get(f"/api/public/events/{event_id}")
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "Board games in the park"


async def test_the_public_page_returns_only_safe_fields(client, make_user):
    """The field list IS the privacy boundary, so it is asserted exactly."""
    _, event_id = await _host_with_event(make_user)

    body = (await client.get(f"/api/public/events/{event_id}")).json()
    assert set(body) == {
        "id",
        "kind",
        "title",
        "description",
        "starts_at",
        "ends_at",
        "address",
        "neighborhood",
        "host_name",
        "tag_name",
    }
    # Named explicitly so adding any of these later fails loudly.
    for leak in ("host_id", "location", "capacity", "participant_count", "visibility"):
        assert leak not in body


async def test_a_help_requests_address_is_never_public(client, make_user):
    """For a help request the address is somebody's home. Withheld regardless of
    the visibility setting."""
    _, event_id = await _host_with_event(
        make_user, kind="help_request", address="12 Rose Terrace", visibility="public"
    )

    body = (await client.get(f"/api/public/events/{event_id}")).json()
    assert body["kind"] == "help_request"
    assert body["address"] is None
    assert "Rose Terrace" not in str(body)


async def test_a_gatherings_venue_is_public(client, make_user):
    """A host who chose public visibility and typed a venue wants people to
    find it."""
    _, event_id = await _host_with_event(
        make_user, kind="gathering", address="41st St entrance", visibility="public"
    )

    body = (await client.get(f"/api/public/events/{event_id}")).json()
    assert body["address"] == "41st St entrance"


@pytest.mark.parametrize("visibility", ["community", "private"])
async def test_only_public_events_are_publicly_readable(
    client, make_user, community_id, visibility
):
    _, event_id = await _host_with_event(
        make_user, community=community_id, visibility=visibility
    )
    r = await client.get(f"/api/public/events/{event_id}")
    assert r.status_code == 404


async def test_a_cancelled_event_stops_being_publicly_readable(client, make_user):
    """A flyer outlives the event it advertises. Someone scanning last week's
    poster should not be told a cancelled event is still on."""
    host, event_id = await _host_with_event(make_user)
    assert (await client.get(f"/api/public/events/{event_id}")).status_code == 200

    r = await host.patch(f"/api/events/{event_id}", json={"status": "cancelled"})
    assert r.status_code == 200, r.text
    assert (await client.get(f"/api/public/events/{event_id}")).status_code == 404


async def test_an_unknown_event_and_a_hidden_one_look_identical(client, make_user):
    """A stranger probing ids must not be able to tell "no such event" from
    "exists but not for you"."""
    _, private_id = await _host_with_event(make_user, visibility="private")
    missing = "11111111-2222-3333-4444-555555555555"

    hidden = await client.get(f"/api/public/events/{private_id}")
    unknown = await client.get(f"/api/public/events/{missing}")
    assert hidden.status_code == unknown.status_code == 404
    assert hidden.json() == unknown.json()


# ---- the templated fallback itself -----------------------------------------


def test_fallback_copy_stays_within_the_layout_limits():
    long_title = "A very long title " * 12
    copy = fallback_copy(
        title=long_title,
        description="X" * 900,
        host_name="Marcus",
        neighborhood="Sunset Park",
        starts_at=datetime.now(timezone.utc) + timedelta(days=3),
        kind="gathering",
    )
    assert copy.generated is False
    for option in copy.options:
        assert len(option.headline) <= MAX_HEADLINE_CHARS
        assert len(option.blurb) <= MAX_BLURB_CHARS


def test_fallback_copy_invents_nothing_and_survives_missing_fields():
    starts = datetime(2026, 8, 15, 15, 0, tzinfo=timezone.utc)
    copy = fallback_copy(
        title="Board games in the park",
        description=None,
        host_name=None,
        neighborhood=None,
        starts_at=starts,
        kind="gathering",
    )
    assert copy.options
    joined = " ".join(o.headline + " " + o.blurb for o in copy.options)
    # Everything in the output traces back to an input or a fixed phrase.
    assert "Board games in the park" in joined
    assert "None" not in joined
