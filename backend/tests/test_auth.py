"""Registration, login, sessions, CSRF, and account deletion."""


async def test_register_creates_user_and_profile(make_user):
    dylan = await make_user("dylan@example.com", "Dylan")
    me = (await dylan.get("/api/users/me")).json()
    assert me["email"] == "dylan@example.com"
    profile = (await dylan.get("/api/profiles/me")).json()
    assert profile["display_name"] == "Dylan"


async def test_duplicate_email_rejected(client, make_user):
    await make_user("dylan@example.com", "Dylan")
    r = await client.post(
        "/api/auth/register",
        json={"email": "dylan@example.com", "password": "whatever-123", "display_name": "X"},
    )
    assert r.status_code == 400
    assert "message" in r.json()


async def test_password_rules(client):
    r = await client.post(
        "/api/auth/register",
        json={"email": "a@example.com", "password": "short", "display_name": "A"},
    )
    assert r.status_code == 422

    r = await client.post(
        "/api/auth/register",
        json={"email": "b@example.com", "password": "b@example.com", "display_name": "B"},
    )
    assert r.status_code == 422  # password must not equal email


async def test_bad_credentials(client, make_user):
    await make_user("dylan@example.com", "Dylan")
    r = await client.post(
        "/api/auth/login",
        json={"email": "dylan@example.com", "password": "wrong-password"},
    )
    assert r.status_code == 400


async def test_me_requires_auth(client):
    r = await client.get("/api/users/me")
    assert r.status_code == 401


async def test_csrf_required_for_mutations(make_user):
    dylan = await make_user("dylan@example.com", "Dylan")
    r = await dylan.patch(
        "/api/profiles/me",
        json={"bio": "hi"},
        headers={"X-CSRF-Token": "forged-value"},
    )
    assert r.status_code == 403

    r = await dylan.patch("/api/profiles/me", json={"bio": "hi"})
    assert r.status_code == 200  # correct header from the fixture passes


async def test_logout_revokes_session_server_side(make_user, client):
    dylan = await make_user("dylan@example.com", "Dylan")
    # Steal the cookie value like an attacker who copied it pre-logout.
    stolen = dylan.cookies.get("ours_auth")

    r = await dylan.post("/api/auth/logout")
    assert r.status_code == 204

    # The stolen token must be dead: the DB row was destroyed, not just
    # the browser cookie cleared.
    client.cookies.set("ours_auth", stolen)
    r = await client.get("/api/users/me")
    assert r.status_code == 401


async def test_delete_account(make_user, client):
    dylan = await make_user("dylan@example.com", "Dylan")
    r = await dylan.delete("/api/users/me")
    assert r.status_code == 204
    r = await client.post(
        "/api/auth/login",
        json={"email": "dylan@example.com", "password": "password-123"},
    )
    assert r.status_code == 400
