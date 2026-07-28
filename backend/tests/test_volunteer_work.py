"""Volunteer work: the organization counterpart to a personal help request.

An individual asks a neighbour for a favour (help_request); an organization
recruits for a shift (volunteer_work). Each account type is offered only the one
that fits, and either way the person who asked confirms who actually turned up —
which is what makes the public "helped" tally trustworthy.
"""

from tests.conftest import event_payload
from tests.test_orgs import register_and_confirm

PAST = {"starts_at": "2020-06-01T15:00:00Z", "ends_at": "2020-06-01T18:00:00Z"}
ORG_SIGNUP = {
    "account_type": "organization",
    "org_category": "parks",
    "org_website": "https://parks.example",
}


async def user_id(client):
    return (await client.get("/api/users/me")).json()["id"]


async def org_client(make_org, email="parks@ci.brooklyn.gov", name="Parks Dept"):
    return await make_org(email, name)


# --- who may post what -----------------------------------------------------

async def test_person_cannot_post_volunteer_work(make_user):
    someone = await make_user("someone@example.com", "Someone")
    r = await someone.post(
        "/api/events", json=event_payload(kind="volunteer_work", title="Tree planting")
    )
    assert r.status_code == 403
    assert "organization" in r.json()["message"].lower()


async def test_organization_can_post_volunteer_work(make_org):
    org = await make_org("parks@ci.brooklyn.gov", "Parks Dept")
    r = await org.post(
        "/api/events", json=event_payload(kind="volunteer_work", title="Tree planting")
    )
    assert r.status_code == 201
    assert r.json()["kind"] == "volunteer_work"


async def test_organization_cannot_post_a_help_request(make_org):
    """Orgs recruit volunteers rather than asking for a personal favour."""
    org = await make_org("parks@ci.brooklyn.gov", "Parks Dept")
    r = await org.post(
        "/api/events", json=event_payload(kind="help_request", title="Move a shelf")
    )
    assert r.status_code == 403


async def test_everyone_can_still_post_gatherings(make_user, make_org):
    someone = await make_user("someone@example.com", "Someone")
    org = await make_org("parks@ci.brooklyn.gov", "Parks Dept")
    for client in (someone, org):
        r = await client.post("/api/events", json=event_payload())
        assert r.status_code == 201


async def test_people_keep_help_requests(make_user):
    someone = await make_user("someone@example.com", "Someone")
    r = await someone.post(
        "/api/events", json=event_payload(kind="help_request", title="Ride to the pharmacy")
    )
    assert r.status_code == 201


# --- confirming volunteers -------------------------------------------------

async def test_org_confirms_volunteers_and_it_counts_as_helped(make_org, make_user):
    org = await make_org("parks@ci.brooklyn.gov", "Parks Dept")
    volunteer = await make_user("vol@example.com", "Volunteer")
    vol_id = await user_id(volunteer)

    event = (
        await org.post(
            "/api/events",
            json=event_payload(kind="volunteer_work", title="Tree planting", **PAST),
        )
    ).json()
    await volunteer.put(f"/api/events/{event['id']}/rsvp", json={"status": "going"})

    r = await org.post(
        f"/api/events/{event['id']}/thanks",
        json={"helper_id": vol_id, "note": "Forty trees in the ground!"},
    )
    assert r.status_code == 201

    record = (await volunteer.get(f"/api/profiles/{vol_id}/trust")).json()
    assert record["helped"] == 1


async def test_volunteer_notification_says_volunteered(make_org, make_user):
    org = await make_org("parks@ci.brooklyn.gov", "Parks Dept")
    volunteer = await make_user("vol@example.com", "Volunteer")
    vol_id = await user_id(volunteer)

    event = (
        await org.post(
            "/api/events",
            json=event_payload(kind="volunteer_work", title="Tree planting", **PAST),
        )
    ).json()
    await volunteer.put(f"/api/events/{event['id']}/rsvp", json={"status": "going"})
    await org.post(f"/api/events/{event['id']}/thanks", json={"helper_id": vol_id})

    note = next(
        n for n in (await volunteer.get("/api/notifications")).json()
        if n["type"] == "help_thanks"
    )
    # Wording differs from a neighbour's personal thank-you.
    assert "volunteered" in note["message"]
    assert "Tree planting" in note["message"]


async def test_a_volunteer_cannot_confirm_themselves(make_org, make_user):
    org = await make_org("parks@ci.brooklyn.gov", "Parks Dept")
    volunteer = await make_user("vol@example.com", "Volunteer")
    vol_id = await user_id(volunteer)

    event = (
        await org.post(
            "/api/events",
            json=event_payload(kind="volunteer_work", title="Tree planting", **PAST),
        )
    ).json()
    await volunteer.put(f"/api/events/{event['id']}/rsvp", json={"status": "going"})

    r = await volunteer.post(
        f"/api/events/{event['id']}/thanks", json={"helper_id": vol_id}
    )
    assert r.status_code == 403
    record = (await volunteer.get(f"/api/profiles/{vol_id}/trust")).json()
    assert record["helped"] == 0


async def test_thanks_still_refused_on_a_gathering(make_org, make_user):
    org = await make_org("parks@ci.brooklyn.gov", "Parks Dept")
    guest = await make_user("guest@example.com", "Guest")
    event = (await org.post("/api/events", json=event_payload(**PAST))).json()
    await guest.put(f"/api/events/{event['id']}/rsvp", json={"status": "going"})

    r = await org.post(
        f"/api/events/{event['id']}/thanks", json={"helper_id": await user_id(guest)}
    )
    assert r.status_code == 409


async def test_volunteer_work_appears_on_the_map(make_org, make_user):
    org = await make_org("parks@ci.brooklyn.gov", "Parks Dept")
    await org.post(
        "/api/events", json=event_payload(kind="volunteer_work", title="Tree planting")
    )
    viewer = await make_user("viewer@example.com", "Viewer")
    nearby = (
        await viewer.get("/api/events?lat=40.6552&lng=-74.0069&radius_m=3000")
    ).json()
    planting = next(e for e in nearby if e["title"] == "Tree planting")
    assert planting["kind"] == "volunteer_work"


async def test_map_can_filter_to_volunteer_work(make_org, make_user):
    org = await make_org("parks@ci.brooklyn.gov", "Parks Dept")
    await org.post(
        "/api/events", json=event_payload(kind="volunteer_work", title="Tree planting")
    )
    await org.post("/api/events", json=event_payload(title="Just a picnic"))

    viewer = await make_user("viewer@example.com", "Viewer")
    only = (
        await viewer.get(
            "/api/events?lat=40.6552&lng=-74.0069&radius_m=3000&kind=volunteer_work"
        )
    ).json()
    titles = {e["title"] for e in only}
    assert "Tree planting" in titles
    assert "Just a picnic" not in titles
