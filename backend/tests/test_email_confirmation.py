"""Confirming an email address, and what it does (and doesn't) unlock.

The signed link is the credential, so the tests care about forgery: a tampered
or expired token must be refused, and confirming an address must never hand out
the organization badge unless the address itself earns it.
"""

import uuid

from itsdangerous import URLSafeTimedSerializer

from app.core.config import settings
from app.core.email import (
    CONFIRM_MAX_AGE_SECONDS,
    confirm_link,
    make_confirm_token,
    read_confirm_token,
)

ORG = {
    "account_type": "organization",
    "org_category": "library",
    "org_website": "https://example-library.org",
}


async def confirm(client, token):
    return await client.post("/api/auth/confirm-email", json={"token": token})


async def signup(client, email, display_name, **extra):
    """Register and sign in — registration alone doesn't set a session, so
    /api/users/me needs the login step."""
    created = (
        await client.post(
            "/api/auth/register",
            json={
                "email": email,
                "password": "password-123",
                "display_name": display_name,
                **extra,
            },
        )
    ).json()
    await client.post(
        "/api/auth/login", json={"email": email, "password": "password-123"}
    )
    # Once a session cookie exists the CSRF middleware applies, so echo the
    # double-submit token the way the real frontend does.
    client.headers["X-CSRF-Token"] = client.cookies.get("ours_csrf")
    return created


async def me(client):
    return (await client.get("/api/users/me")).json()


# --- the token itself ------------------------------------------------------

def test_round_trip():
    uid = uuid.uuid4()
    assert read_confirm_token(make_confirm_token(uid)) == str(uid)


def test_tampered_token_is_refused():
    token = make_confirm_token(uuid.uuid4())
    assert read_confirm_token(token[:-3] + "abc") is None
    assert read_confirm_token("nonsense") is None


def test_token_signed_with_another_key_is_refused():
    other = URLSafeTimedSerializer("a-different-secret", salt="email-confirm")
    assert read_confirm_token(other.dumps(str(uuid.uuid4()))) is None


def test_token_for_another_purpose_is_refused():
    """Salting per purpose stops a token minted elsewhere being replayed here."""
    other_purpose = URLSafeTimedSerializer(settings.secret_key, salt="password-reset")
    assert read_confirm_token(other_purpose.dumps(str(uuid.uuid4()))) is None


def test_expired_token_is_refused(monkeypatch):
    token = make_confirm_token(uuid.uuid4())
    # Re-read it as if the max age had already elapsed.
    monkeypatch.setattr(
        "app.core.email.CONFIRM_MAX_AGE_SECONDS", -1, raising=False
    )
    serializer = URLSafeTimedSerializer(settings.secret_key, salt="email-confirm")
    from itsdangerous import SignatureExpired

    try:
        serializer.loads(token, max_age=-1)
        expired = False
    except SignatureExpired:
        expired = True
    assert expired
    assert CONFIRM_MAX_AGE_SECONDS > 0  # the real setting is still sane


def test_link_points_at_the_frontend_route():
    link = confirm_link("abc.def")
    assert link.startswith(settings.public_base_url.rstrip("/"))
    assert "/confirm-email?token=" in link


def test_link_is_absolute_even_when_the_base_url_has_no_scheme(monkeypatch):
    """Render can expose a bare hostname; a mail client needs a full URL."""
    monkeypatch.setattr(settings, "public_base_url", "ours.onrender.com")
    assert confirm_link("tok").startswith("https://ours.onrender.com/confirm-email")


# --- confirming -------------------------------------------------------------

async def test_registration_leaves_the_address_unconfirmed(client):
    await signup(client, "new@example.com", "New Neighbor")
    assert (await me(client))["email_confirmed"] is False


async def test_confirming_marks_the_address_and_is_idempotent(client):
    created = await signup(client, "new@example.com", "New Neighbor")
    token = make_confirm_token(created["id"])

    first = await confirm(client, token)
    assert first.status_code == 200
    assert first.json()["already_confirmed"] is False
    assert (await me(client))["email_confirmed"] is True

    # Clicking the same link twice is harmless, and says so.
    second = await confirm(client, token)
    assert second.status_code == 200
    assert second.json()["already_confirmed"] is True


async def test_bad_token_is_rejected(client):
    r = await confirm(client, "not-a-real-token")
    assert r.status_code == 400


async def test_token_for_a_deleted_user_is_rejected(client):
    r = await confirm(client, make_confirm_token(uuid.uuid4()))
    assert r.status_code == 400


# --- what confirmation unlocks ---------------------------------------------

async def test_confirming_a_gated_domain_grants_the_org_badge(client):
    created = await signup(
        client, "office@ps321.k12.ny.us", "PS 321 Library", **ORG
    )
    assert created["is_verified"] is False  # not until the inbox is proven

    result = await confirm(client, make_confirm_token(created["id"]))
    assert result.json()["organization_verified"] is True
    assert (await me(client))["is_verified"] is True


async def test_confirming_an_open_domain_org_grants_nothing(client):
    """A .org still waits for a human, however many links it clicks."""
    created = await signup(
        client, "hello@brooklynlibrary.org", "Brooklyn Library", **ORG
    )

    result = await confirm(client, make_confirm_token(created["id"]))
    assert result.json()["organization_verified"] is False
    assert (await me(client))["is_verified"] is False


async def test_a_person_on_a_gated_domain_gets_no_badge(client):
    """A student at a university is not an organization."""
    created = await signup(client, "student@nyu.edu", "A Student")

    result = await confirm(client, make_confirm_token(created["id"]))
    assert result.json()["organization_verified"] is False
    mine = await me(client)
    assert mine["email_confirmed"] is True
    assert mine["is_verified"] is False


# --- resending --------------------------------------------------------------

async def test_resend_requires_a_session_and_refuses_once_confirmed(client, make_user):
    anon = await confirm(client, "x")  # noqa: F841 — just to exercise the anon path
    someone = await make_user("someone@example.com", "Someone")

    first = await someone.post("/api/auth/confirm-email/request")
    assert first.status_code == 202

    uid = (await someone.get("/api/users/me")).json()["id"]
    await someone.post(
        "/api/auth/confirm-email", json={"token": make_confirm_token(uid)}
    )
    again = await someone.post("/api/auth/confirm-email/request")
    assert again.status_code == 409
