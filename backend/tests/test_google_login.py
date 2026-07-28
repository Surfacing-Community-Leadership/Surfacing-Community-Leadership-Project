"""Signing in with Google.

The risky parts are the state parameter (the CSRF guard on the callback) and
what a successful sign-in is allowed to grant. Google's verified email may set
email_confirmed_at; it must never set org_verified, or every Gmail account would
arrive wearing an organization badge.

Google itself is stubbed — these tests exercise our handling, not Google's.
"""

import uuid

import pytest
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.oauth import GoogleError, authorize_url, make_state, read_state
from app.models import OAuthAccount, Profile, User

CALLBACK = "/api/auth/google/callback"


@pytest.fixture(autouse=True)
def google_configured(monkeypatch):
    """Pretend a Google client is configured for every test in this module."""
    monkeypatch.setattr(settings, "google_client_id", "test-client-id")
    monkeypatch.setattr(settings, "google_client_secret", "test-secret")


def stub_google(monkeypatch, *, sub="google-sub-1", email="neighbor@gmail.com",
                email_verified=True, name="A Neighbor"):
    async def fake_exchange(code):
        if code == "bad-code":
            raise GoogleError("Google rejected the sign-in")
        return {
            "sub": sub,
            "email": email,
            "email_verified": email_verified,
            "name": name,
        }

    monkeypatch.setattr("app.routers.auth.exchange_code_for_profile", fake_exchange)


async def user_by_email(email):
    async with AsyncSessionLocal() as session:
        return await session.scalar(select(User).where(User.email == email))


async def oauth_links(email):
    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.email == email))
        if user is None:
            return []
        return (
            await session.scalars(
                select(OAuthAccount).where(OAuthAccount.user_id == user.id)
            )
        ).all()


# --- configuration gate ----------------------------------------------------

async def test_provider_list_reports_google(client):
    assert (await client.get("/api/auth/providers")).json()["google"] is True


async def test_disabled_when_unconfigured(client, monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", None)
    assert (await client.get("/api/auth/providers")).json()["google"] is False
    r = await client.get("/api/auth/google/start")
    assert r.status_code == 503


# --- the state parameter ---------------------------------------------------

def test_state_round_trip_carries_the_destination():
    parsed = read_state(make_state("/events/new"))
    assert parsed["next"] == "/events/new"
    assert parsed["nonce"]


def test_tampered_or_foreign_state_is_refused():
    assert read_state("garbage") is None
    foreign = URLSafeTimedSerializer("another-secret", salt="google-oauth-state")
    assert read_state(foreign.dumps({"nonce": "x", "next": "/map"})) is None


def test_authorize_url_requests_only_identity_scopes():
    url = authorize_url(make_state())
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "scope=openid+email+profile" in url
    # No Gmail/Drive/contacts access.
    assert "gmail" not in url and "drive" not in url


async def test_start_redirects_to_google(client):
    r = await client.get("/api/auth/google/start", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"].startswith("https://accounts.google.com/")


async def test_start_refuses_an_offsite_next(client):
    r = await client.get(
        "/api/auth/google/start?next=https://evil.example/steal",
        follow_redirects=False,
    )
    # The hostile destination is dropped, not signed into the state.
    assert read_state(
        r.headers["location"].split("state=")[1].split("&")[0]
    )["next"] == "/map"


async def test_callback_without_valid_state_is_refused(client, monkeypatch):
    stub_google(monkeypatch)
    r = await client.get(
        f"{CALLBACK}?code=abc&state=forged", follow_redirects=False
    )
    assert r.status_code == 303
    assert "/login?error=" in r.headers["location"]
    # Nothing was created.
    assert await user_by_email("neighbor@gmail.com") is None


async def test_cancelled_consent_redirects_with_a_message(client):
    r = await client.get(
        f"{CALLBACK}?error=access_denied&state={make_state()}", follow_redirects=False
    )
    assert "/login?error=" in r.headers["location"]


async def test_google_failure_is_surfaced_not_leaked(client, monkeypatch):
    stub_google(monkeypatch)
    r = await client.get(
        f"{CALLBACK}?code=bad-code&state={make_state()}", follow_redirects=False
    )
    assert "/login?error=" in r.headers["location"]


# --- first sign-in ---------------------------------------------------------

async def test_first_sign_in_creates_a_confirmed_personal_account(client, monkeypatch):
    stub_google(monkeypatch)
    r = await client.get(
        f"{CALLBACK}?code=good&state={make_state()}", follow_redirects=False
    )
    assert r.status_code == 303
    # New accounts land in onboarding.
    assert r.headers["location"] == "/onboarding"

    user = await user_by_email("neighbor@gmail.com")
    assert user is not None
    # Google vouched for the address, so it counts as confirmed…
    assert user.email_confirmed_at is not None
    # …but signing in never earns the organization badge.
    assert user.org_verified is False

    async with AsyncSessionLocal() as session:
        profile = await session.scalar(
            select(Profile).where(Profile.user_id == user.id)
        )
    assert profile.display_name == "A Neighbor"
    assert profile.account_type == "person"


async def test_sign_in_sets_a_session(client, monkeypatch):
    stub_google(monkeypatch)
    await client.get(f"{CALLBACK}?code=good&state={make_state()}", follow_redirects=False)
    client.headers["X-CSRF-Token"] = client.cookies.get("ours_csrf")
    me = (await client.get("/api/users/me")).json()
    assert me["email"] == "neighbor@gmail.com"
    assert me["email_confirmed"] is True
    assert me["org_verified"] is False


async def test_unverified_google_email_is_not_treated_as_confirmed(client, monkeypatch):
    stub_google(monkeypatch, email_verified=False)
    await client.get(f"{CALLBACK}?code=good&state={make_state()}", follow_redirects=False)
    user = await user_by_email("neighbor@gmail.com")
    assert user.email_confirmed_at is None


async def test_returning_sign_in_reuses_the_same_account(client, monkeypatch):
    stub_google(monkeypatch)
    first = await client.get(
        f"{CALLBACK}?code=good&state={make_state()}", follow_redirects=False
    )
    assert first.headers["location"] == "/onboarding"

    second = await client.get(
        f"{CALLBACK}?code=good&state={make_state('/map')}", follow_redirects=False
    )
    # Not new any more, so it honours the requested destination.
    assert second.headers["location"] == "/map"
    assert len(await oauth_links("neighbor@gmail.com")) == 1


async def test_identity_is_pinned_to_the_subject_not_the_email(client, monkeypatch):
    """Changing the Google address keeps the same local account."""
    stub_google(monkeypatch)
    await client.get(f"{CALLBACK}?code=good&state={make_state()}", follow_redirects=False)
    original = await user_by_email("neighbor@gmail.com")

    stub_google(monkeypatch, email="renamed@gmail.com")
    await client.get(f"{CALLBACK}?code=good&state={make_state()}", follow_redirects=False)
    # No second account appeared under the new address.
    assert await user_by_email("renamed@gmail.com") is None
    assert (await user_by_email("neighbor@gmail.com")).id == original.id


# --- meeting an existing password account ----------------------------------

async def test_verified_google_email_links_to_an_existing_account(
    client, make_user, monkeypatch
):
    await make_user("shared@example.com", "Already Here")
    stub_google(monkeypatch, email="shared@example.com", sub="google-sub-9")

    r = await client.get(
        f"{CALLBACK}?code=good&state={make_state()}", follow_redirects=False
    )
    assert r.status_code == 303
    assert "/login?error=" not in r.headers["location"]
    links = await oauth_links("shared@example.com")
    assert len(links) == 1
    assert links[0].provider == "google"


async def test_unverified_google_email_cannot_take_over_an_account(
    client, make_user, monkeypatch
):
    """The account-takeover guard: without Google vouching for the address,
    claiming someone else's email must not hand over their account."""
    await make_user("victim@example.com", "Victim")
    stub_google(
        monkeypatch, email="victim@example.com", sub="attacker-sub", email_verified=False
    )

    r = await client.get(
        f"{CALLBACK}?code=good&state={make_state()}", follow_redirects=False
    )
    assert "/login?error=" in r.headers["location"]
    assert await oauth_links("victim@example.com") == []


async def test_google_never_grants_an_org_badge_even_on_a_gated_domain(
    client, monkeypatch
):
    """A school email signing in with Google is still just a person here —
    organizations register through the email form."""
    stub_google(monkeypatch, email="teacher@ps321.k12.ny.us", sub="school-sub")
    await client.get(f"{CALLBACK}?code=good&state={make_state()}", follow_redirects=False)

    user = await user_by_email("teacher@ps321.k12.ny.us")
    assert user.email_confirmed_at is not None
    assert user.org_verified is False
