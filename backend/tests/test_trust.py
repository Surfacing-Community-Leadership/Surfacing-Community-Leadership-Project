"""Self-confirmed attendance, help thanks, and the public track record.

These counts are shown publicly and confer a tier, so the tests lean on the
rules that stop them being farmed: the event must be over, the reflection must
be substantial, nothing can be confirmed twice, and "helped" can only ever be
written by the neighbor who asked for help.
"""

from tests.conftest import event_payload

# 25 words — comfortably over MIN_REFLECTION_WORDS.
REFLECTION = (
    "We met by the swings and ended up talking for a long while about the "
    "block and its history, then swapped numbers before heading home."
)
PAST = {"starts_at": "2020-06-01T15:00:00Z", "ends_at": "2020-06-01T18:00:00Z"}


async def user_id(client):
    return (await client.get("/api/users/me")).json()["id"]


async def trust(client, uid):
    return (await client.get(f"/api/profiles/{uid}/trust")).json()


# --- attendance ------------------------------------------------------------

async def test_cannot_confirm_before_event_is_over(make_user):
    host = await make_user("host@example.com", "Host")
    guest = await make_user("guest@example.com", "Guest")
    # Default payload starts in 2027.
    event = (await host.post("/api/events", json=event_payload())).json()

    r = await guest.post(
        f"/api/events/{event['id']}/attendance", json={"reflection": REFLECTION}
    )
    assert r.status_code == 409


async def test_reflection_must_be_long_enough(make_user):
    host = await make_user("host@example.com", "Host")
    guest = await make_user("guest@example.com", "Guest")
    event = (await host.post("/api/events", json=event_payload(**PAST))).json()

    r = await guest.post(
        f"/api/events/{event['id']}/attendance", json={"reflection": "Went and it was fine."}
    )
    assert r.status_code == 422


async def test_confirming_attendance_counts_once(make_user):
    host = await make_user("host@example.com", "Host")
    guest = await make_user("guest@example.com", "Guest")
    guest_id = await user_id(guest)
    event = (await host.post("/api/events", json=event_payload(**PAST))).json()

    r = await guest.post(
        f"/api/events/{event['id']}/attendance", json={"reflection": REFLECTION}
    )
    assert r.status_code == 201
    assert (await trust(guest, guest_id))["attended"] == 1

    # A second confirmation for the same event can't pad the count.
    again = await guest.post(
        f"/api/events/{event['id']}/attendance", json={"reflection": REFLECTION}
    )
    assert again.status_code == 409
    assert (await trust(guest, guest_id))["attended"] == 1


async def test_attendance_needs_no_prior_rsvp(make_user):
    """You might have found the event on the map and simply gone."""
    host = await make_user("host@example.com", "Host")
    walkin = await make_user("walkin@example.com", "Walk-in")
    event = (await host.post("/api/events", json=event_payload(**PAST))).json()

    r = await walkin.post(
        f"/api/events/{event['id']}/attendance", json={"reflection": REFLECTION}
    )
    assert r.status_code == 201


async def test_host_does_not_self_confirm(make_user):
    host = await make_user("host@example.com", "Host")
    event = (await host.post("/api/events", json=event_payload(**PAST))).json()

    r = await host.post(
        f"/api/events/{event['id']}/attendance", json={"reflection": REFLECTION}
    )
    assert r.status_code == 409


async def test_reflection_stays_private(make_user):
    """The reflection is friction and a personal record — never shown to others."""
    host = await make_user("host@example.com", "Host")
    guest = await make_user("guest@example.com", "Guest")
    event = (await host.post("/api/events", json=event_payload(**PAST))).json()
    await guest.post(
        f"/api/events/{event['id']}/attendance", json={"reflection": REFLECTION}
    )

    listing = (await host.get(f"/api/events/{event['id']}/participants")).json()
    assert REFLECTION not in str(listing)


# --- help thanks -----------------------------------------------------------

async def _finished_help_request(requester, helper):
    """A past help request the helper RSVP'd to."""
    event = (
        await requester.post(
            "/api/events", json=event_payload(kind="help_request", title="Move a shelf", **PAST)
        )
    ).json()
    await helper.put(f"/api/events/{event['id']}/rsvp", json={"status": "going"})
    return event


async def test_thanks_counts_help_and_notifies_with_note(make_user):
    asker = await make_user("asker@example.com", "Asker")
    helper = await make_user("helper@example.com", "Helper")
    helper_id = await user_id(helper)
    event = await _finished_help_request(asker, helper)

    r = await asker.post(
        f"/api/events/{event['id']}/thanks",
        json={"helper_id": helper_id, "note": "Lifesaver — thank you!"},
    )
    assert r.status_code == 201
    assert (await trust(helper, helper_id))["helped"] == 1

    notes = [
        n for n in (await helper.get("/api/notifications")).json()
        if n["type"] == "help_thanks"
    ]
    assert len(notes) == 1
    assert "Lifesaver" in notes[0]["message"]


async def test_only_the_asker_can_say_thanks(make_user):
    asker = await make_user("asker@example.com", "Asker")
    helper = await make_user("helper@example.com", "Helper")
    bystander = await make_user("by@example.com", "Bystander")
    helper_id = await user_id(helper)
    event = await _finished_help_request(asker, helper)

    # The helper cannot award it to themselves...
    mine = await helper.post(
        f"/api/events/{event['id']}/thanks", json={"helper_id": helper_id}
    )
    assert mine.status_code == 403
    # ...nor can an unrelated neighbor hand it out.
    theirs = await bystander.post(
        f"/api/events/{event['id']}/thanks", json={"helper_id": helper_id}
    )
    assert theirs.status_code == 403
    assert (await trust(helper, helper_id))["helped"] == 0


async def test_thanks_is_once_per_helper(make_user):
    asker = await make_user("asker@example.com", "Asker")
    helper = await make_user("helper@example.com", "Helper")
    helper_id = await user_id(helper)
    event = await _finished_help_request(asker, helper)

    first = await asker.post(
        f"/api/events/{event['id']}/thanks", json={"helper_id": helper_id}
    )
    assert first.status_code == 201
    second = await asker.post(
        f"/api/events/{event['id']}/thanks", json={"helper_id": helper_id}
    )
    assert second.status_code == 409
    assert (await trust(helper, helper_id))["helped"] == 1


async def test_cannot_thank_someone_who_was_not_involved(make_user):
    asker = await make_user("asker@example.com", "Asker")
    helper = await make_user("helper@example.com", "Helper")
    stranger = await make_user("stranger@example.com", "Stranger")
    event = await _finished_help_request(asker, helper)

    r = await asker.post(
        f"/api/events/{event['id']}/thanks", json={"helper_id": await user_id(stranger)}
    )
    assert r.status_code == 404


async def test_thanks_only_on_help_requests(make_user):
    host = await make_user("host@example.com", "Host")
    guest = await make_user("guest@example.com", "Guest")
    event = (await host.post("/api/events", json=event_payload(**PAST))).json()
    await guest.put(f"/api/events/{event['id']}/rsvp", json={"status": "going"})

    r = await host.post(
        f"/api/events/{event['id']}/thanks", json={"helper_id": await user_id(guest)}
    )
    assert r.status_code == 409


# --- the record itself -----------------------------------------------------

async def test_hosting_counts_only_once_the_event_has_started(make_user):
    host = await make_user("host@example.com", "Host")
    host_id = await user_id(host)

    await host.post("/api/events", json=event_payload())  # 2027 — not yet
    assert (await trust(host, host_id))["hosted"] == 0
    assert (await trust(host, host_id))["tier"] == "Neighbor"

    await host.post("/api/events", json=event_payload(**PAST))
    record = await trust(host, host_id)
    assert record["hosted"] == 1
    assert record["tier"] == "Host"


async def test_cancelled_events_do_not_count_as_hosted(make_user):
    host = await make_user("host@example.com", "Host")
    host_id = await user_id(host)
    event = (await host.post("/api/events", json=event_payload(**PAST))).json()
    assert (await trust(host, host_id))["hosted"] == 1

    await host.patch(f"/api/events/{event['id']}", json={"status": "cancelled"})
    assert (await trust(host, host_id))["hosted"] == 0


async def test_tier_reaches_organizer_and_reports_verified(make_user):
    host = await make_user("host@example.com", "Host")
    host_id = await user_id(host)
    for i in range(5):
        await host.post("/api/events", json=event_payload(title=f"Past {i}", **PAST))

    record = await trust(host, host_id)
    assert record["hosted"] == 5
    assert record["tier"] == "Organizer"
    # Verification is a separate, admin-granted signal — off by default.
    assert record["verified"] is False


async def test_helper_tier_from_confirmed_help(make_user):
    helper = await make_user("helper@example.com", "Helper")
    helper_id = await user_id(helper)
    askers = [await make_user(f"a{i}@example.com", f"Asker {i}") for i in range(3)]

    for asker in askers:
        event = await _finished_help_request(asker, helper)
        await asker.post(
            f"/api/events/{event['id']}/thanks", json={"helper_id": helper_id}
        )

    record = await trust(helper, helper_id)
    assert record["helped"] == 3
    assert record["tier"] == "Helper"
