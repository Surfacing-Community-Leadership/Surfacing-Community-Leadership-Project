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
