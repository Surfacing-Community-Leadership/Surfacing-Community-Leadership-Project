"""Following organizations, and the notifications that follow from it.

The delicate part is the fan-out: a follower must only hear about a post they
could actually open, so private events notify nobody and community-only events
reach only followers in that community.
"""

from tests.conftest import event_payload

PAST = {"starts_at": "2020-06-01T15:00:00Z", "ends_at": "2020-06-01T18:00:00Z"}


async def user_id(client):
    return (await client.get("/api/users/me")).json()["id"]


async def org_events(client):
    return [
        n for n in (await client.get("/api/notifications")).json()
        if n["type"] == "org_event"
    ]


# --- following -------------------------------------------------------------

async def test_follow_and_unfollow_an_organization(make_org, make_user):
    org = await make_org("library@ci.brooklyn.gov", "Central Library")
    org_id = await user_id(org)
    someone = await make_user("someone@example.com", "Someone")

    state = (await someone.put(f"/api/organizations/{org_id}/follow")).json()
    assert state == {"following": True, "followers": 1}

    state = (await someone.get(f"/api/organizations/{org_id}/follow")).json()
    assert state["following"] is True

    state = (await someone.delete(f"/api/organizations/{org_id}/follow")).json()
    assert state == {"following": False, "followers": 0}


async def test_following_is_idempotent(make_org, make_user):
    org = await make_org("library@ci.brooklyn.gov", "Central Library")
    org_id = await user_id(org)
    someone = await make_user("someone@example.com", "Someone")

    await someone.put(f"/api/organizations/{org_id}/follow")
    again = (await someone.put(f"/api/organizations/{org_id}/follow")).json()
    # A double tap must not inflate the count or error.
    assert again == {"following": True, "followers": 1}

    await someone.delete(f"/api/organizations/{org_id}/follow")
    twice = (await someone.delete(f"/api/organizations/{org_id}/follow")).json()
    assert twice == {"following": False, "followers": 0}


async def test_people_cannot_be_followed(make_user):
    """Following is for institutions; person-to-person is connections."""
    a = await make_user("a@example.com", "Ann")
    b = await make_user("b@example.com", "Bo")
    r = await a.put(f"/api/organizations/{await user_id(b)}/follow")
    assert r.status_code == 404


async def test_an_org_cannot_follow_itself(make_org):
    org = await make_org("library@ci.brooklyn.gov", "Central Library")
    r = await org.put(f"/api/organizations/{await user_id(org)}/follow")
    assert r.status_code == 409


async def test_blocked_accounts_cannot_be_followed(make_org, make_user):
    org = await make_org("library@ci.brooklyn.gov", "Central Library")
    org_id = await user_id(org)
    someone = await make_user("someone@example.com", "Someone")
    await someone.post("/api/blocks", json={"blocked_id": org_id})

    r = await someone.put(f"/api/organizations/{org_id}/follow")
    assert r.status_code == 403


# --- browsing --------------------------------------------------------------

async def test_directory_lists_orgs_verified_first_with_follow_state(
    make_org, make_user, client
):
    verified = await make_org("gov@ci.brooklyn.gov", "Parks Department")
    verified_id = await user_id(verified)
    # A .org signup stays unverified until an admin checks it.
    await client.post(
        "/api/auth/register",
        json={
            "email": "unverified@someplace.org",
            "password": "password-123",
            "display_name": "Aardvark Society",
            "account_type": "organization",
            "org_category": "nonprofit",
            "org_website": "https://someplace.org",
        },
    )
    someone = await make_user("someone@example.com", "Someone")
    await someone.put(f"/api/organizations/{verified_id}/follow")

    listing = (await someone.get("/api/organizations")).json()
    names = [o["display_name"] for o in listing]
    assert "Parks Department" in names and "Aardvark Society" in names
    # Verified leads, despite being alphabetically later.
    assert names.index("Parks Department") < names.index("Aardvark Society")

    parks = next(o for o in listing if o["display_name"] == "Parks Department")
    assert parks["verified"] is True
    assert parks["following"] is True
    assert parks["followers"] == 1


async def test_directory_can_filter_to_what_you_follow(make_org, make_user):
    followed = await make_org("gov@ci.brooklyn.gov", "Parks Department")
    other = await make_org("school@ps321.k12.ny.us", "PS 321")  # noqa: F841
    someone = await make_user("someone@example.com", "Someone")
    await someone.put(f"/api/organizations/{await user_id(followed)}/follow")

    mine = (await someone.get("/api/organizations?following=true")).json()
    assert [o["display_name"] for o in mine] == ["Parks Department"]

    rest = (await someone.get("/api/organizations?following=false")).json()
    assert "Parks Department" not in [o["display_name"] for o in rest]


async def test_people_do_not_appear_in_the_directory(make_org, make_user):
    await make_org("gov@ci.brooklyn.gov", "Parks Department")
    someone = await make_user("someone@example.com", "Someone")
    listing = (await someone.get("/api/organizations")).json()
    assert "Someone" not in [o["display_name"] for o in listing]


# --- notifications on new posts --------------------------------------------

async def test_followers_hear_about_a_new_gathering(make_org, make_user):
    org = await make_org("library@ci.brooklyn.gov", "Central Library")
    follower = await make_user("f@example.com", "Follower")
    await follower.put(f"/api/organizations/{await user_id(org)}/follow")

    await org.post("/api/events", json=event_payload(title="Story time"))

    notes = await org_events(follower)
    assert len(notes) == 1
    assert "Central Library posted a gathering: Story time" == notes[0]["message"]


async def test_volunteer_work_is_named_as_such(make_org, make_user):
    org = await make_org("parks@ci.brooklyn.gov", "Parks Department")
    follower = await make_user("f@example.com", "Follower")
    await follower.put(f"/api/organizations/{await user_id(org)}/follow")

    await org.post(
        "/api/events", json=event_payload(kind="volunteer_work", title="Tree planting")
    )

    notes = await org_events(follower)
    assert "posted volunteer work: Tree planting" in notes[0]["message"]


async def test_non_followers_hear_nothing(make_org, make_user):
    org = await make_org("library@ci.brooklyn.gov", "Central Library")
    stranger = await make_user("s@example.com", "Stranger")
    await org.post("/api/events", json=event_payload(title="Story time"))
    assert await org_events(stranger) == []


async def test_unfollowing_stops_the_notifications(make_org, make_user):
    org = await make_org("library@ci.brooklyn.gov", "Central Library")
    org_id = await user_id(org)
    follower = await make_user("f@example.com", "Follower")

    await follower.put(f"/api/organizations/{org_id}/follow")
    await org.post("/api/events", json=event_payload(title="First"))
    await follower.delete(f"/api/organizations/{org_id}/follow")
    await org.post("/api/events", json=event_payload(title="Second"))

    messages = [n["message"] for n in await org_events(follower)]
    assert any("First" in m for m in messages)
    assert not any("Second" in m for m in messages)


async def test_private_events_notify_nobody(make_org, make_user):
    """Invite-only by definition — announcing it would defeat the point."""
    org = await make_org("library@ci.brooklyn.gov", "Central Library")
    follower = await make_user("f@example.com", "Follower")
    await follower.put(f"/api/organizations/{await user_id(org)}/follow")

    await org.post(
        "/api/events", json=event_payload(title="Board meeting", visibility="private")
    )
    assert await org_events(follower) == []


async def test_community_events_only_reach_that_community(
    make_org, make_user, community_id
):
    org = await make_org("library@ci.brooklyn.gov", "Central Library")
    org_id = await user_id(org)
    await org.patch("/api/profiles/me", json={"community_id": community_id})

    insider = await make_user("in@example.com", "Insider")
    await insider.patch("/api/profiles/me", json={"community_id": community_id})
    outsider = await make_user("out@example.com", "Outsider")

    for follower in (insider, outsider):
        await follower.put(f"/api/organizations/{org_id}/follow")

    await org.post(
        "/api/events",
        json=event_payload(title="Members only", visibility="community"),
    )

    assert len(await org_events(insider)) == 1
    assert await org_events(outsider) == []


async def test_a_persons_events_notify_nobody(make_user):
    """Only organizations fan out — a neighbour's picnic isn't broadcast."""
    person = await make_user("p@example.com", "Person")
    watcher = await make_user("w@example.com", "Watcher")
    await person.post("/api/events", json=event_payload(title="My picnic"))
    assert await org_events(watcher) == []


async def test_blocked_followers_are_skipped(make_org, make_user):
    org = await make_org("library@ci.brooklyn.gov", "Central Library")
    org_id = await user_id(org)
    follower = await make_user("f@example.com", "Follower")
    await follower.put(f"/api/organizations/{org_id}/follow")
    # The follower later blocks the organization.
    await follower.post("/api/blocks", json={"blocked_id": org_id})

    await org.post("/api/events", json=event_payload(title="Story time"))
    assert await org_events(follower) == []
