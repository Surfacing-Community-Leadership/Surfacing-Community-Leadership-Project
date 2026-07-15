"""Events: creation, discovery, visibility, RSVPs, capacity, lifecycle."""

from datetime import datetime, timedelta, timezone

from tests.conftest import event_payload

NEARBY = "/api/events?lat=40.6552&lng=-74.0069&radius_m=3000"
FAR_AWAY = "/api/events?lat=40.7580&lng=-73.9855&radius_m=1000"  # Times Sq


async def test_create_and_discover(make_user):
    dylan = await make_user("dylan@example.com", "Dylan")
    r = await dylan.post("/api/events", json=event_payload())
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "open"  # server default came back

    found = (await dylan.get(NEARBY)).json()
    assert [e["id"] for e in found] == [body["id"]]
    assert found[0]["distance_m"] is not None

    assert (await dylan.get(FAR_AWAY)).json() == []


async def test_ends_before_start_rejected(make_user):
    dylan = await make_user("dylan@example.com", "Dylan")
    r = await dylan.post(
        "/api/events",
        json=event_payload(
            starts_at="2027-08-01T15:00:00Z", ends_at="2027-08-01T14:00:00Z"
        ),
    )
    assert r.status_code == 422


async def test_private_event_hidden_until_invited(make_user):
    eleanor = await make_user("eleanor@example.com", "Eleanor")
    dylan = await make_user("dylan@example.com", "Dylan")
    event = (
        await eleanor.post("/api/events", json=event_payload(visibility="private"))
    ).json()

    assert (await dylan.get(NEARBY)).json() == []
    assert (await dylan.get(f"/api/events/{event['id']}")).status_code == 404

    # Connect, then invite — the event becomes visible.
    dylan_id = (await dylan.get("/api/users/me")).json()["id"]
    conn = (
        await dylan.post(
            "/api/connections",
            json={"addressee_id": (await eleanor.get("/api/users/me")).json()["id"]},
        )
    ).json()
    await eleanor.patch(f"/api/connections/{conn['id']}", json={"status": "accepted"})
    r = await eleanor.post(f"/api/events/{event['id']}/invites", json={"user_id": dylan_id})
    assert r.status_code == 201
    assert (await dylan.get(f"/api/events/{event['id']}")).status_code == 200


async def test_address_revealed_only_when_going(make_user):
    dylan = await make_user("dylan@example.com", "Dylan")
    eleanor = await make_user("eleanor@example.com", "Eleanor")
    event = (await dylan.post("/api/events", json=event_payload())).json()

    detail = (await eleanor.get(f"/api/events/{event['id']}")).json()
    assert detail["address"] is None

    await eleanor.put(f"/api/events/{event['id']}/rsvp", json={"status": "going"})
    detail = (await eleanor.get(f"/api/events/{event['id']}")).json()
    assert detail["address"] == "41st St entrance"


async def test_capacity_enforced(make_user):
    dylan = await make_user("dylan@example.com", "Dylan")
    eleanor = await make_user("eleanor@example.com", "Eleanor")
    mitch = await make_user("mitch@example.com", "Mitch")
    event = (await dylan.post("/api/events", json=event_payload(capacity=1))).json()

    r = await eleanor.put(f"/api/events/{event['id']}/rsvp", json={"status": "going"})
    assert r.status_code == 200
    r = await mitch.put(f"/api/events/{event['id']}/rsvp", json={"status": "going"})
    assert r.status_code == 409
    # 'maybe' doesn't take a confirmed seat, so it's still allowed.
    r = await mitch.put(f"/api/events/{event['id']}/rsvp", json={"status": "maybe"})
    assert r.status_code == 200


async def test_only_host_may_edit_or_delete(make_user):
    dylan = await make_user("dylan@example.com", "Dylan")
    eleanor = await make_user("eleanor@example.com", "Eleanor")
    event = (await dylan.post("/api/events", json=event_payload())).json()

    r = await eleanor.patch(f"/api/events/{event['id']}", json={"title": "Hijacked"})
    assert r.status_code == 403
    r = await eleanor.delete(f"/api/events/{event['id']}")
    assert r.status_code == 403
    r = await dylan.delete(f"/api/events/{event['id']}")
    assert r.status_code == 204
    assert (await dylan.get(f"/api/events/{event['id']}")).status_code == 404


async def test_status_state_machine(make_user):
    dylan = await make_user("dylan@example.com", "Dylan")
    event = (await dylan.post("/api/events", json=event_payload())).json()
    url = f"/api/events/{event['id']}"

    r = await dylan.patch(url, json={"status": "cancelled"})
    assert r.status_code == 200
    # cancelled is terminal
    r = await dylan.patch(url, json={"status": "open"})
    assert r.status_code == 409


async def test_rsvp_on_cancelled_event_rejected(make_user):
    dylan = await make_user("dylan@example.com", "Dylan")
    eleanor = await make_user("eleanor@example.com", "Eleanor")
    event = (await dylan.post("/api/events", json=event_payload())).json()
    await dylan.patch(f"/api/events/{event['id']}", json={"status": "cancelled"})

    r = await eleanor.put(f"/api/events/{event['id']}/rsvp", json={"status": "going"})
    assert r.status_code == 409


async def test_blocks_hide_events(make_user):
    eleanor = await make_user("eleanor@example.com", "Eleanor")
    bob = await make_user("bob@example.com", "Bob")
    event = (await eleanor.post("/api/events", json=event_payload())).json()
    bob_id = (await bob.get("/api/users/me")).json()["id"]

    assert len((await bob.get(NEARBY)).json()) == 1
    await eleanor.post("/api/blocks", json={"blocked_id": bob_id})

    assert (await bob.get(NEARBY)).json() == []
    assert (await bob.get(f"/api/events/{event['id']}")).status_code == 404


async def test_discovery_pagination(make_user):
    dylan = await make_user("dylan@example.com", "Dylan")
    for i in range(3):
        await dylan.post("/api/events", json=event_payload(title=f"Event {i}"))

    page1 = (await dylan.get(f"{NEARBY}&limit=2")).json()
    page2 = (await dylan.get(f"{NEARBY}&limit=2&offset=2")).json()
    assert len(page1) == 2
    assert len(page2) == 1
    assert {e["id"] for e in page1}.isdisjoint({e["id"] for e in page2})


async def test_event_happening_now_still_shows(make_user):
    # Regression: an event created to start a few minutes ago (i.e. now) must
    # not vanish from the map — it's ongoing, not past.
    dylan = await make_user("dylan@example.com", "Dylan")
    recent = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
    await dylan.post("/api/events", json=event_payload(title="Bagels now", starts_at=recent))
    found = (await dylan.get(NEARBY)).json()
    assert any(e["title"] == "Bagels now" for e in found)


async def test_long_finished_event_hidden(make_user):
    # An event whose (assumed) end is well in the past should drop off.
    dylan = await make_user("dylan@example.com", "Dylan")
    old = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
    await dylan.post("/api/events", json=event_payload(title="This morning", starts_at=old))
    found = (await dylan.get(NEARBY)).json()
    assert not any(e["title"] == "This morning" for e in found)


async def test_ongoing_event_with_end_time_shows_until_it_ends(make_user):
    # Started an hour ago, ends in an hour → still ongoing → visible.
    dylan = await make_user("dylan@example.com", "Dylan")
    started = datetime.now(timezone.utc) - timedelta(hours=1)
    ends = datetime.now(timezone.utc) + timedelta(hours=1)
    await dylan.post(
        "/api/events",
        json=event_payload(
            title="Long picnic", starts_at=started.isoformat(), ends_at=ends.isoformat()
        ),
    )
    found = (await dylan.get(NEARBY)).json()
    assert any(e["title"] == "Long picnic" for e in found)


async def test_my_events_lists_only_my_creations(make_user):
    dylan = await make_user("dylan@example.com", "Dylan")
    eleanor = await make_user("eleanor@example.com", "Eleanor")
    await dylan.post("/api/events", json=event_payload(title="Mine A"))
    await dylan.post("/api/events", json=event_payload(kind="help_request", title="Mine B"))
    await eleanor.post("/api/events", json=event_payload(title="Not mine"))

    mine = (await dylan.get("/api/users/me/events")).json()
    assert {e["title"] for e in mine} == {"Mine A", "Mine B"}


async def test_my_events_includes_cancelled(make_user):
    # Unlike the map, this list shows events in any status.
    dylan = await make_user("dylan@example.com", "Dylan")
    ev = (await dylan.post("/api/events", json=event_payload(title="Called off"))).json()
    await dylan.patch(f"/api/events/{ev['id']}", json={"status": "cancelled"})

    mine = (await dylan.get("/api/users/me/events")).json()
    assert [e["title"] for e in mine] == ["Called off"]
    assert mine[0]["status"] == "cancelled"
