"""Connections, search, blocks, messages, interests, reports."""

from tests.conftest import event_payload


async def user_id(client):
    return (await client.get("/api/users/me")).json()["id"]


async def connect(requester, addressee):
    """Create an accepted connection between two user-clients."""
    conn = (
        await requester.post(
            "/api/connections", json={"addressee_id": await user_id(addressee)}
        )
    ).json()
    r = await addressee.patch(f"/api/connections/{conn['id']}", json={"status": "accepted"})
    assert r.status_code == 200
    return conn


async def test_connection_lifecycle(make_user):
    dylan = await make_user("dylan@example.com", "Dylan")
    eleanor = await make_user("eleanor@example.com", "Eleanor")

    r = await dylan.post("/api/connections", json={"addressee_id": await user_id(dylan)})
    assert r.status_code == 422  # can't connect with yourself

    conn = (
        await dylan.post("/api/connections", json={"addressee_id": await user_id(eleanor)})
    ).json()

    # duplicates rejected in both directions
    r = await dylan.post("/api/connections", json={"addressee_id": await user_id(eleanor)})
    assert r.status_code == 409
    r = await eleanor.post("/api/connections", json={"addressee_id": await user_id(dylan)})
    assert r.status_code == 409

    # only the addressee may accept
    r = await dylan.patch(f"/api/connections/{conn['id']}", json={"status": "accepted"})
    assert r.status_code == 403
    r = await eleanor.patch(f"/api/connections/{conn['id']}", json={"status": "accepted"})
    assert r.status_code == 200

    friends = (await dylan.get("/api/connections")).json()
    assert [f["display_name"] for f in friends] == ["Eleanor"]

    r = await eleanor.delete(f"/api/connections/{conn['id']}")
    assert r.status_code == 204
    assert (await dylan.get("/api/connections")).json() == []


async def test_people_search(make_user):
    dylan = await make_user("dylan@example.com", "Dylan")
    await make_user("eleanor@example.com", "Eleanor")

    results = (await dylan.get("/api/profiles?q=elea")).json()
    assert [p["display_name"] for p in results] == ["Eleanor"]

    # never yourself
    results = (await dylan.get("/api/profiles?q=dyl")).json()
    assert results == []

    r = await dylan.get("/api/profiles?q=e")
    assert r.status_code == 422  # too short


async def test_block_severs_and_hides(make_user):
    eleanor = await make_user("eleanor@example.com", "Eleanor")
    bob = await make_user("bob@example.com", "Bob")
    await connect(bob, eleanor)

    r = await eleanor.post("/api/blocks", json={"blocked_id": await user_id(bob)})
    assert r.status_code == 201

    # connection gone, re-request refused, search finds nothing
    assert (await eleanor.get("/api/connections")).json() == []
    r = await bob.post("/api/connections", json={"addressee_id": await user_id(eleanor)})
    assert r.status_code == 403
    assert (await bob.get("/api/profiles?q=Eleanor")).json() == []

    # unblock restores the request path
    r = await eleanor.delete(f"/api/blocks/{await user_id(bob)}")
    assert r.status_code == 204
    r = await bob.post("/api/connections", json={"addressee_id": await user_id(eleanor)})
    assert r.status_code == 201


async def test_block_hides_profile_both_ways(make_user):
    eleanor = await make_user("eleanor@example.com", "Eleanor")
    bob = await make_user("bob@example.com", "Bob")
    eleanor_id, bob_id = await user_id(eleanor), await user_id(bob)
    await eleanor.post("/api/blocks", json={"blocked_id": bob_id})

    # Neither can open the other's profile by direct URL (404, not 403).
    assert (await bob.get(f"/api/profiles/{eleanor_id}")).status_code == 404
    assert (await eleanor.get(f"/api/profiles/{bob_id}")).status_code == 404


async def test_block_removes_participation_in_hosts_event(make_user):
    host = await make_user("host@example.com", "Host")
    guest = await make_user("guest@example.com", "Guest")
    guest_id = await user_id(guest)
    event = (await host.post("/api/events", json=event_payload())).json()
    await guest.put(f"/api/events/{event['id']}/rsvp", json={"status": "going"})

    await host.post("/api/blocks", json={"blocked_id": guest_id})

    parts = (await host.get(f"/api/events/{event['id']}/participants")).json()
    assert all(p["user_id"] != guest_id for p in parts)


async def test_block_hides_each_other_in_third_party_event(make_user):
    host = await make_user("host@example.com", "Host")
    ann = await make_user("ann@example.com", "Ann")
    bo = await make_user("bo@example.com", "Bo")
    ann_id, bo_id = await user_id(ann), await user_id(bo)
    event = (await host.post("/api/events", json=event_payload())).json()
    eid = event["id"]
    for c in (ann, bo):
        await c.put(f"/api/events/{eid}/rsvp", json={"status": "going"})
    await ann.post(f"/api/events/{eid}/messages", json={"body": "hi from Ann"})
    await bo.post(f"/api/events/{eid}/messages", json={"body": "hi from Bo"})

    await ann.post("/api/blocks", json={"blocked_id": bo_id})

    # Both remain in the host's event, but each is filtered from the other's
    # view of the participant and message lists.
    ann_parts = (await ann.get(f"/api/events/{eid}/participants")).json()
    assert all(p["user_id"] != bo_id for p in ann_parts)
    ann_msgs = (await ann.get(f"/api/events/{eid}/messages")).json()
    assert all(m["sender_id"] != bo_id for m in ann_msgs)
    bo_parts = (await bo.get(f"/api/events/{eid}/participants")).json()
    assert all(p["user_id"] != ann_id for p in bo_parts)


async def test_event_messages_scoped_to_participants(make_user):
    dylan = await make_user("dylan@example.com", "Dylan")
    eleanor = await make_user("eleanor@example.com", "Eleanor")
    bob = await make_user("bob@example.com", "Bob")
    event = (await dylan.post("/api/events", json=event_payload())).json()
    url = f"/api/events/{event['id']}/messages"

    await eleanor.put(f"/api/events/{event['id']}/rsvp", json={"status": "going"})
    r = await eleanor.post(url, json={"body": "Should I bring a chair?"})
    assert r.status_code == 201

    messages = (await dylan.get(url)).json()  # host reads
    assert len(messages) == 1
    assert messages[0]["display_name"] == "Eleanor"

    r = await bob.post(url, json={"body": "hello"})  # outsider
    assert r.status_code == 403
    r = await bob.get(url)
    assert r.status_code == 403


async def test_interests_roundtrip(make_user, interest_id):
    dylan = await make_user("dylan@example.com", "Dylan")

    r = await dylan.put("/api/profiles/me/interests", json={"interest_ids": [interest_id]})
    assert r.status_code == 200
    got = (await dylan.get("/api/profiles/me/interests")).json()
    assert got["interest_ids"] == [interest_id]

    r = await dylan.put("/api/profiles/me/interests", json={"interest_ids": []})
    assert r.status_code == 200
    assert (await dylan.get("/api/profiles/me/interests")).json()["interest_ids"] == []


async def test_reports(make_user):
    dylan = await make_user("dylan@example.com", "Dylan")
    eleanor = await make_user("eleanor@example.com", "Eleanor")

    r = await dylan.post("/api/reports", json={"reason": "no target"})
    assert r.status_code == 422

    r = await dylan.post(
        "/api/reports",
        json={"reported_user_id": await user_id(eleanor), "reason": "spam"},
    )
    assert r.status_code == 201
    assert r.json()["status"] == "open"
