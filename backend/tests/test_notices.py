"""The notice board.

Posting needs three things — a neighborhood, a confirmed email, and a free slot
in the allowance — so most tests go through `board_user`, which arranges all
three. The interesting cases are the ones that take one of them away.
"""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.email import make_confirm_token
from app.core.notices import DEFAULT_EXPIRY_DAYS, MAX_EXPIRY_DAYS, MAX_LIVE_NOTICES
from app.main import app
from tests.conftest import BASE_URL


def notice_payload(**overrides):
    payload = {
        "category": "giveaway",
        "title": "Free bookshelf",
        "body": "Solid pine, two shelves, needs a wipe down. On the stoop.",
        "place_hint": "44th St between 5th and 6th",
    }
    payload.update(overrides)
    return payload


@pytest.fixture
async def board_user(community_id):
    """Factory for an account that can actually post: registered, logged in,
    email confirmed, and living in `community_id`."""
    clients = []

    async def factory(email, name="Neighbor", *, community=community_id, confirm=True):
        c = AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL)
        clients.append(c)
        r = await c.post(
            "/api/auth/register",
            json={"email": email, "password": "password-123", "display_name": name},
        )
        assert r.status_code == 201, r.text
        created = r.json()
        r = await c.post(
            "/api/auth/login", json={"email": email, "password": "password-123"}
        )
        assert r.status_code == 204, r.text
        c.headers["X-CSRF-Token"] = c.cookies.get("ours_csrf")
        if confirm:
            r = await c.post(
                "/api/auth/confirm-email",
                json={"token": make_confirm_token(created["id"])},
            )
            assert r.status_code == 200, r.text
        if community is not None:
            r = await c.patch("/api/profiles/me", json={"community_id": community})
            assert r.status_code == 200, r.text
        return c

    yield factory
    for c in clients:
        await c.aclose()


# ---- posting ---------------------------------------------------------------


async def test_a_neighbor_posts_a_notice_and_it_appears_on_the_board(board_user):
    author = await board_user("author@example.com", "Ada")
    reader = await board_user("reader@example.com", "Ben")

    r = await author.post("/api/notices", json=notice_payload())
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["title"] == "Free bookshelf"
    assert created["author_name"] == "Ada"
    assert created["resolved"] is False

    r = await reader.get("/api/notices")
    assert r.status_code == 200
    board = r.json()
    assert [n["id"] for n in board] == [created["id"]]
    assert board[0]["author_name"] == "Ada"


async def test_a_notice_defaults_to_the_standard_expiry_window(board_user):
    author = await board_user("author@example.com")
    r = await author.post("/api/notices", json=notice_payload())
    expires = datetime.fromisoformat(r.json()["expires_at"])
    expected = datetime.now(timezone.utc) + timedelta(days=DEFAULT_EXPIRY_DAYS)
    assert abs((expires - expected).total_seconds()) < 60


async def test_an_over_long_expiry_is_clamped_not_rejected(board_user):
    author = await board_user("author@example.com")
    far_future = datetime.now(timezone.utc) + timedelta(days=365)
    r = await author.post(
        "/api/notices",
        json=notice_payload(expires_at=far_future.isoformat()),
    )
    assert r.status_code == 201, r.text
    expires = datetime.fromisoformat(r.json()["expires_at"])
    cap = datetime.now(timezone.utc) + timedelta(days=MAX_EXPIRY_DAYS)
    assert abs((expires - cap).total_seconds()) < 60


async def test_posting_needs_a_neighborhood(board_user):
    nomad = await board_user("nomad@example.com", community=None)
    r = await nomad.post("/api/notices", json=notice_payload())
    assert r.status_code == 409
    assert "neighborhood" in r.json()["message"].lower()


async def test_posting_needs_a_confirmed_email(board_user):
    unconfirmed = await board_user("new@example.com", confirm=False)
    r = await unconfirmed.post("/api/notices", json=notice_payload())
    assert r.status_code == 403
    assert "confirm" in r.json()["message"].lower()


async def test_the_allowance_caps_live_notices(board_user):
    author = await board_user("author@example.com")
    for i in range(MAX_LIVE_NOTICES):
        r = await author.post("/api/notices", json=notice_payload(title=f"Item {i}"))
        assert r.status_code == 201, r.text

    r = await author.post("/api/notices", json=notice_payload(title="One too many"))
    assert r.status_code == 409
    assert str(MAX_LIVE_NOTICES) in r.json()["message"]


async def test_resolving_a_notice_frees_a_slot(board_user):
    author = await board_user("author@example.com")
    ids = []
    for i in range(MAX_LIVE_NOTICES):
        r = await author.post("/api/notices", json=notice_payload(title=f"Item {i}"))
        ids.append(r.json()["id"])

    r = await author.patch(f"/api/notices/{ids[0]}", json={"resolved": True})
    assert r.status_code == 200
    assert r.json()["resolved"] is True

    r = await author.post("/api/notices", json=notice_payload(title="Now there's room"))
    assert r.status_code == 201, r.text


async def test_a_body_that_says_nothing_is_rejected(board_user):
    author = await board_user("author@example.com")
    r = await author.post("/api/notices", json=notice_payload(body="couch"))
    assert r.status_code == 422


# ---- categories ------------------------------------------------------------


async def test_a_person_cannot_post_an_organization_category(board_user):
    author = await board_user("author@example.com")
    r = await author.post("/api/notices", json=notice_payload(category="announcement"))
    assert r.status_code == 403
    assert "organization" in r.json()["message"].lower()


async def test_an_organization_can_post_an_announcement(make_org, community_id):
    library = await make_org("library@brooklyn.gov", "Sunset Park Library")
    r = await library.patch("/api/profiles/me", json={"community_id": community_id})
    assert r.status_code == 200

    r = await library.post(
        "/api/notices",
        json=notice_payload(
            category="announcement",
            title="Summer reading starts Monday",
            body="Sign-ups open at the front desk all week. Ages 4 and up.",
        ),
    )
    assert r.status_code == 201, r.text
    assert r.json()["author_is_org"] is True
    assert r.json()["author_verified"] is True


async def test_an_organization_can_still_post_a_giveaway(make_org, community_id):
    library = await make_org("library@brooklyn.gov", "Sunset Park Library")
    await library.patch("/api/profiles/me", json={"community_id": community_id})
    r = await library.post("/api/notices", json=notice_payload())
    assert r.status_code == 201, r.text


async def test_there_is_no_crime_or_safety_category(board_user):
    """A product decision, asserted so nobody adds one by reflex later: see the
    module docstring in app/core/notices.py for why."""
    author = await board_user("author@example.com")
    for category in ("crime", "safety", "crime_safety", "suspicious"):
        r = await author.post("/api/notices", json=notice_payload(category=category))
        assert r.status_code == 422, f"{category} was accepted"

    r = await author.get("/api/notices/meta")
    assert not any(
        "crime" in c or "safety" in c or "suspicious" in c
        for c in r.json()["categories"]
    )


# ---- what the board shows --------------------------------------------------


async def test_the_board_is_scoped_to_your_own_neighborhood(board_user):
    from app.models import Community
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        other = Community(name="Bay Ridge", slug="bay-ridge")
        session.add(other)
        await session.commit()
        await session.refresh(other)
        other_id = str(other.id)

    here = await board_user("here@example.com", "Local")
    away = await board_user("away@example.com", "Elsewhere", community=other_id)

    r = await here.post("/api/notices", json=notice_payload())
    assert r.status_code == 201

    # The other neighborhood's board doesn't carry it.
    assert (await away.get("/api/notices")).json() == []
    assert len((await here.get("/api/notices")).json()) == 1


async def test_an_expired_notice_leaves_the_board(board_user):
    from app.core.database import AsyncSessionLocal
    from app.models import Notice
    from sqlalchemy import select

    author = await board_user("author@example.com")
    reader = await board_user("reader@example.com")
    r = await author.post("/api/notices", json=notice_payload())
    notice_id = r.json()["id"]

    # Reach past the API: there's deliberately no way to post something
    # already expired.
    async with AsyncSessionLocal() as session:
        notice = await session.scalar(select(Notice).where(Notice.id == notice_id))
        notice.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await session.commit()

    assert (await reader.get("/api/notices")).json() == []
    # The author still sees it, so they can repost or extend it.
    mine = (await author.get("/api/notices?mine=true")).json()
    assert [n["id"] for n in mine] == [notice_id]


async def test_a_resolved_notice_is_hidden_unless_asked_for(board_user):
    author = await board_user("author@example.com")
    reader = await board_user("reader@example.com")
    r = await author.post("/api/notices", json=notice_payload())
    notice_id = r.json()["id"]
    await author.patch(f"/api/notices/{notice_id}", json={"resolved": True})

    assert (await reader.get("/api/notices")).json() == []
    shown = (await reader.get("/api/notices?include_resolved=true")).json()
    assert [n["id"] for n in shown] == [notice_id]


async def test_a_blocked_neighbors_notices_disappear(board_user):
    author = await board_user("author@example.com", "Ada")
    reader = await board_user("reader@example.com", "Ben")
    r = await author.post("/api/notices", json=notice_payload())
    notice_id = r.json()["id"]

    me = (await author.get("/api/users/me")).json()
    r = await reader.post("/api/blocks", json={"blocked_id": me["id"]})
    assert r.status_code in (201, 204), r.text

    assert (await reader.get("/api/notices")).json() == []
    # And it's not reachable directly either.
    assert (await reader.get(f"/api/notices/{notice_id}")).status_code == 404


async def test_filtering_the_board_by_category(board_user):
    author = await board_user("author@example.com")
    await author.post("/api/notices", json=notice_payload(category="giveaway"))
    await author.post(
        "/api/notices",
        json=notice_payload(
            category="lost_found",
            title="Found: grey cat",
            body="Very friendly, no collar, hanging around the corner store.",
        ),
    )

    found = (await author.get("/api/notices?category=lost_found")).json()
    assert [n["title"] for n in found] == ["Found: grey cat"]


# ---- replies ---------------------------------------------------------------


async def test_a_reply_reaches_the_author_privately(board_user):
    author = await board_user("author@example.com", "Ada")
    reader = await board_user("reader@example.com", "Ben")
    notice_id = (await author.post("/api/notices", json=notice_payload())).json()["id"]

    r = await reader.post(
        f"/api/notices/{notice_id}/replies", json={"body": "I'd love the bookshelf."}
    )
    assert r.status_code == 201, r.text
    assert r.json()["author_name"] == "Ben"

    # The author reads it...
    replies = (await author.get(f"/api/notices/{notice_id}/replies")).json()
    assert [x["body"] for x in replies] == ["I'd love the bookshelf."]

    # ...and gets one notification pointing at the board.
    notes = (await author.get("/api/notifications")).json()
    assert [n["type"] for n in notes] == ["notice_reply"]
    assert "Ben replied to your notice" in notes[0]["message"]
    assert notes[0]["link"] == f"/board/{notice_id}"


async def test_nobody_else_can_read_the_replies(board_user):
    author = await board_user("author@example.com")
    reader = await board_user("reader@example.com")
    nosy = await board_user("nosy@example.com")
    notice_id = (await author.post("/api/notices", json=notice_payload())).json()["id"]
    await reader.post(f"/api/notices/{notice_id}/replies", json={"body": "Yes please!"})

    r = await nosy.get(f"/api/notices/{notice_id}/replies")
    assert r.status_code == 403
    # The reply count is the author's business too.
    board = (await nosy.get("/api/notices")).json()
    assert board[0]["reply_count"] is None
    mine = (await author.get("/api/notices?mine=true")).json()
    assert mine[0]["reply_count"] == 1


async def test_replying_twice_edits_and_does_not_ping_again(board_user):
    author = await board_user("author@example.com")
    reader = await board_user("reader@example.com")
    notice_id = (await author.post("/api/notices", json=notice_payload())).json()["id"]

    await reader.post(f"/api/notices/{notice_id}/replies", json={"body": "First try."})
    r = await reader.post(
        f"/api/notices/{notice_id}/replies", json={"body": "Actually, still keen."}
    )
    assert r.status_code == 201, r.text

    replies = (await author.get(f"/api/notices/{notice_id}/replies")).json()
    assert [x["body"] for x in replies] == ["Actually, still keen."]
    # One neighbor, one ping — editing must not become an unlimited pinger.
    notes = (await author.get("/api/notifications")).json()
    assert len(notes) == 1


async def test_you_cannot_reply_to_your_own_notice(board_user):
    author = await board_user("author@example.com")
    notice_id = (await author.post("/api/notices", json=notice_payload())).json()["id"]
    r = await author.post(f"/api/notices/{notice_id}/replies", json={"body": "Hello me"})
    assert r.status_code == 409


async def test_a_resolved_notice_stops_taking_replies(board_user):
    author = await board_user("author@example.com")
    reader = await board_user("reader@example.com")
    notice_id = (await author.post("/api/notices", json=notice_payload())).json()["id"]
    await author.patch(f"/api/notices/{notice_id}", json={"resolved": True})

    r = await reader.post(f"/api/notices/{notice_id}/replies", json={"body": "Too late?"})
    assert r.status_code == 409
    assert "closed" in r.json()["message"].lower()


async def test_a_neighbor_from_another_board_cannot_reply(board_user):
    from app.core.database import AsyncSessionLocal
    from app.models import Community

    async with AsyncSessionLocal() as session:
        other = Community(name="Bay Ridge", slug="bay-ridge")
        session.add(other)
        await session.commit()
        await session.refresh(other)
        other_id = str(other.id)

    author = await board_user("author@example.com")
    away = await board_user("away@example.com", community=other_id)
    notice_id = (await author.post("/api/notices", json=notice_payload())).json()["id"]

    r = await away.post(f"/api/notices/{notice_id}/replies", json={"body": "Me!"})
    assert r.status_code == 404


# ---- editing and deleting --------------------------------------------------


async def test_only_the_author_edits_or_deletes(board_user):
    author = await board_user("author@example.com")
    reader = await board_user("reader@example.com")
    notice_id = (await author.post("/api/notices", json=notice_payload())).json()["id"]

    assert (
        await reader.patch(f"/api/notices/{notice_id}", json={"title": "Mine now"})
    ).status_code == 403
    assert (await reader.delete(f"/api/notices/{notice_id}")).status_code == 403
    assert (await author.delete(f"/api/notices/{notice_id}")).status_code == 204
    assert (await author.get(f"/api/notices/{notice_id}")).status_code == 404


async def test_extending_repeatedly_cannot_make_a_notice_immortal(board_user):
    author = await board_user("author@example.com")
    notice_id = (await author.post("/api/notices", json=notice_payload())).json()["id"]

    cap = datetime.now(timezone.utc) + timedelta(days=MAX_EXPIRY_DAYS)
    for _ in range(3):
        far = datetime.now(timezone.utc) + timedelta(days=200)
        r = await author.patch(
            f"/api/notices/{notice_id}", json={"expires_at": far.isoformat()}
        )
        assert r.status_code == 200, r.text
        expires = datetime.fromisoformat(r.json()["expires_at"])
        assert expires <= cap + timedelta(minutes=1)


async def test_deleting_a_notice_takes_its_reply_notification_with_it(board_user):
    author = await board_user("author@example.com")
    reader = await board_user("reader@example.com")
    notice_id = (await author.post("/api/notices", json=notice_payload())).json()["id"]
    await reader.post(f"/api/notices/{notice_id}/replies", json={"body": "Interested!"})
    assert len((await author.get("/api/notifications")).json()) == 1

    await author.delete(f"/api/notices/{notice_id}")
    # CASCADE, not SET NULL: "someone replied to a notice" with no notice to
    # open is a dead end.
    assert (await author.get("/api/notifications")).json() == []


# ---- board meta ------------------------------------------------------------


async def test_meta_reports_the_allowance_and_why_posting_is_blocked(board_user):
    author = await board_user("author@example.com")
    r = await author.get("/api/notices/meta")
    assert r.status_code == 200
    meta = r.json()
    assert meta["community_name"] == "Sunset Park"
    assert meta["can_post"] is True
    assert meta["live_count"] == 0
    assert meta["max_live"] == MAX_LIVE_NOTICES
    assert "announcement" not in meta["categories"]

    for i in range(MAX_LIVE_NOTICES):
        await author.post("/api/notices", json=notice_payload(title=f"Item {i}"))

    meta = (await author.get("/api/notices/meta")).json()
    assert meta["can_post"] is False
    assert meta["live_count"] == MAX_LIVE_NOTICES
    assert str(MAX_LIVE_NOTICES) in meta["blocked_reason"]


async def test_meta_asks_for_a_neighborhood_rather_than_erroring(board_user):
    nomad = await board_user("nomad@example.com", community=None)
    r = await nomad.get("/api/notices/meta")
    assert r.status_code == 200
    meta = r.json()
    assert meta["community_id"] is None
    assert meta["can_post"] is False
    assert "neighborhood" in meta["blocked_reason"].lower()
    # And the board itself is empty rather than an error.
    assert (await nomad.get("/api/notices")).json() == []


async def test_meta_offers_organizations_the_extra_categories(make_org, community_id):
    library = await make_org("library@brooklyn.gov", "Sunset Park Library")
    await library.patch("/api/profiles/me", json={"community_id": community_id})
    meta = (await library.get("/api/notices/meta")).json()
    assert "announcement" in meta["categories"]
    assert "service_change" in meta["categories"]
    assert "giveaway" in meta["categories"]


# ---- reporting -------------------------------------------------------------


async def test_a_notice_can_be_reported(board_user):
    author = await board_user("author@example.com")
    reader = await board_user("reader@example.com")
    notice_id = (await author.post("/api/notices", json=notice_payload())).json()["id"]

    r = await reader.post(
        "/api/reports",
        json={"reported_notice_id": notice_id, "reason": "spam"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "open"
