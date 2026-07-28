"""Organization accounts and how the ✓ badge is granted.

The badge feeds the trust record on every profile, so the rules that matter are:
declaring "organization" never grants it by itself, only a domain that can't be
casually registered does, and the contact person collected for review is never
public.
"""

import pytest

from app.core.orgs import is_gated_domain, should_auto_verify

LIBRARY = {
    "account_type": "organization",
    "org_category": "library",
    "org_website": "https://brooklynlibrary.org",
    "org_phone": "(718) 555-0134",
    "org_address": "5108 4th Ave, Brooklyn",
    "org_contact_name": "Bob Ellis",
    "org_contact_role": "Programs Director",
}


def org_payload(email, **overrides):
    payload = {
        "email": email,
        "password": "password-123",
        "display_name": "Sunset Park Library",
        **LIBRARY,
    }
    payload.update(overrides)
    return payload


# --- the domain rule in isolation ------------------------------------------

@pytest.mark.parametrize(
    "email,gated",
    [
        ("clerk@ci.brooklyn.gov", True),
        ("dean@nyu.edu", True),
        ("office@ps321.k12.ny.us", True),
        ("staff@some.ac.uk", True),
        # Open registration — anyone can buy these, so they prove nothing.
        ("hello@brooklynlibrary.org", False),
        ("someone@gmail.com", False),
        ("a@notadomain", False),
    ],
)
def test_only_institutional_domains_are_gated(email, gated):
    assert is_gated_domain(email) is gated


def test_personal_accounts_never_auto_verify_even_on_a_gated_domain():
    assert should_auto_verify("person", "dean@nyu.edu") is False
    assert should_auto_verify("organization", "dean@nyu.edu") is True


# --- registration -----------------------------------------------------------

async def test_org_on_gated_domain_is_verified_at_signup(client):
    r = await client.post(
        "/api/auth/register", json=org_payload("office@ps321.k12.ny.us")
    )
    assert r.status_code == 201
    assert r.json()["is_verified"] is True


async def test_org_on_open_domain_starts_unverified(client):
    """A library on a .org is a real org — it just needs a human to check."""
    r = await client.post(
        "/api/auth/register", json=org_payload("hello@brooklynlibrary.org")
    )
    assert r.status_code == 201
    assert r.json()["is_verified"] is False


async def test_claiming_org_does_not_grant_the_badge(client):
    """The whole point: self-declaration is not verification."""
    r = await client.post(
        "/api/auth/register",
        json=org_payload("impostor@gmail.com", display_name="Totally The Library"),
    )
    assert r.status_code == 201
    assert r.json()["is_verified"] is False


async def test_org_signup_requires_category_and_website(client):
    missing_website = org_payload("a@brooklynlibrary.org")
    missing_website["org_website"] = ""
    assert (
        await client.post("/api/auth/register", json=missing_website)
    ).status_code == 422

    bad_category = org_payload("b@brooklynlibrary.org")
    bad_category["org_category"] = "spaceship"
    assert (
        await client.post("/api/auth/register", json=bad_category)
    ).status_code == 422


async def test_personal_signup_ignores_stray_org_fields(client):
    r = await client.post(
        "/api/auth/register",
        json={
            "email": "person@example.com",
            "password": "password-123",
            "display_name": "Just A Neighbor",
            # No account_type — but org fields smuggled in anyway.
            "org_category": "library",
            "org_website": "https://example.org",
        },
    )
    assert r.status_code == 201
    assert r.json()["is_verified"] is False


# --- what other people can see ---------------------------------------------

async def test_public_profile_shows_org_details_but_not_the_contact_person(
    client, make_user
):
    await client.post("/api/auth/register", json=org_payload("office@ps321.k12.ny.us"))
    login = await client.post(
        "/api/auth/login",
        json={"email": "office@ps321.k12.ny.us", "password": "password-123"},
    )
    assert login.status_code == 204
    org_id = (await client.get("/api/users/me")).json()["id"]

    viewer = await make_user("viewer@example.com", "Viewer")
    public = (await viewer.get(f"/api/profiles/{org_id}")).json()

    assert public["account_type"] == "organization"
    assert public["org_category"] == "library"
    assert public["verified"] is True
    assert public["org_phone"] == "(718) 555-0134"
    # Who runs the account is evidence for admins, not a public directory.
    assert "org_contact_name" not in public
    assert "Bob Ellis" not in str(public)


async def test_org_sees_its_own_contact_person(client):
    await client.post("/api/auth/register", json=org_payload("office@ps321.k12.ny.us"))
    await client.post(
        "/api/auth/login",
        json={"email": "office@ps321.k12.ny.us", "password": "password-123"},
    )
    me = (await client.get("/api/profiles/me")).json()
    assert me["org_contact_name"] == "Bob Ellis"
    assert me["org_contact_role"] == "Programs Director"


async def test_search_results_carry_the_org_flags(client, make_user):
    await client.post("/api/auth/register", json=org_payload("office@ps321.k12.ny.us"))
    viewer = await make_user("viewer@example.com", "Viewer")

    hits = (await viewer.get("/api/profiles?q=Sunset")).json()
    org = next(h for h in hits if h["display_name"] == "Sunset Park Library")
    assert org["account_type"] == "organization"
    assert org["verified"] is True


async def test_a_person_profile_reports_person(make_user):
    someone = await make_user("someone@example.com", "Someone")
    me_id = (await someone.get("/api/users/me")).json()["id"]
    other = await make_user("other@example.com", "Other")
    public = (await other.get(f"/api/profiles/{me_id}")).json()
    assert public["account_type"] == "person"
    assert public["verified"] is False
    assert public["org_category"] is None
