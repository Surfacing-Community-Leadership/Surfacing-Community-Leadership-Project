"""The notice board.

Posting needs three things — a neighborhood, a confirmed email, and a free slot
in the allowance — so most tests go through `board_user`, which arranges all
three. The interesting cases are the ones that take one of them away.
"""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.email import make_confirm_token
from app.core.notices import (
    DEFAULT_EXPIRY_DAYS,
    MAX_EXPIRY_DAYS,
    MAX_LIVE_NOTICES,
    MAX_LIVE_NOTICES_ORG,
    STAR_WINDOW_HOURS,
)
from app.main import app
from tests.conftest import BASE_URL

SUNSET_PARK = {"lat": 40.6552, "lng": -74.0069}


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


# ---- the newer post types --------------------------------------------------


@pytest.mark.parametrize("category", ["news", "shoutout", "blog"])
async def test_anyone_can_post_the_read_and_know_types(board_user, category):
    author = await board_user("author@example.com")
    r = await author.post("/api/notices", json=notice_payload(category=category))
    assert r.status_code == 201, r.text
    assert r.json()["category"] == category


async def test_a_long_form_post_is_accepted(board_user):
    """A blog needs more room than a giveaway blurb."""
    author = await board_user("author@example.com")
    r = await author.post(
        "/api/notices",
        json=notice_payload(category="blog", body="The story of our block. " * 200),
    )
    assert r.status_code == 201, r.text
    assert len(r.json()["body"]) > 2000


async def test_an_organization_gets_a_bigger_allowance(make_org, community_id):
    library = await make_org("library@brooklyn.gov", "Sunset Park Library")
    await library.patch("/api/profiles/me", json={"community_id": community_id})

    meta = (await library.get("/api/notices/meta")).json()
    assert meta["max_live"] == MAX_LIVE_NOTICES_ORG
    assert MAX_LIVE_NOTICES_ORG > MAX_LIVE_NOTICES

    # A library really does have more to announce than a neighbour does.
    for i in range(MAX_LIVE_NOTICES + 1):
        r = await library.post(
            "/api/notices", json=notice_payload(category="announcement", title=f"N{i}")
        )
        assert r.status_code == 201, r.text


# ---- stars -----------------------------------------------------------------


async def test_starring_is_one_per_account_and_idempotent(board_user):
    author = await board_user("author@example.com")
    a = await board_user("a@example.com")
    b = await board_user("b@example.com")
    notice_id = (await author.post("/api/notices", json=notice_payload())).json()["id"]

    r = await a.put(f"/api/notices/{notice_id}/star")
    assert r.status_code == 200, r.text
    assert r.json() == {"starred": True, "stars": 1}

    # Starring again is not an error and does not count twice.
    r = await a.put(f"/api/notices/{notice_id}/star")
    assert r.json() == {"starred": True, "stars": 1}

    r = await b.put(f"/api/notices/{notice_id}/star")
    assert r.json() == {"starred": True, "stars": 2}

    # The count is visible to everyone; whose stars they are is visible to nobody.
    board = (await author.get("/api/notices")).json()
    assert board[0]["stars"] == 2
    assert board[0]["i_starred"] is False


async def test_a_star_can_be_taken_back(board_user):
    author = await board_user("author@example.com")
    fan = await board_user("fan@example.com")
    notice_id = (await author.post("/api/notices", json=notice_payload())).json()["id"]

    await fan.put(f"/api/notices/{notice_id}/star")
    r = await fan.delete(f"/api/notices/{notice_id}/star")
    assert r.json() == {"starred": False, "stars": 0}
    # Idempotent both ways.
    r = await fan.delete(f"/api/notices/{notice_id}/star")
    assert r.json() == {"starred": False, "stars": 0}


async def test_i_starred_is_per_viewer(board_user):
    author = await board_user("author@example.com")
    fan = await board_user("fan@example.com")
    other = await board_user("other@example.com")
    notice_id = (await author.post("/api/notices", json=notice_payload())).json()["id"]
    await fan.put(f"/api/notices/{notice_id}/star")

    assert (await fan.get(f"/api/notices/{notice_id}")).json()["i_starred"] is True
    assert (await other.get(f"/api/notices/{notice_id}")).json()["i_starred"] is False


async def test_there_is_no_endpoint_that_reveals_who_starred(board_user):
    """The anonymity is the feature. Asserted so nobody adds a voter list."""
    author = await board_user("author@example.com")
    fan = await board_user("fan@example.com")
    notice_id = (await author.post("/api/notices", json=notice_payload())).json()["id"]
    await fan.put(f"/api/notices/{notice_id}/star")

    # Not even the author gets a list, and no plausible route exists.
    for path in (
        f"/api/notices/{notice_id}/stars",
        f"/api/notices/{notice_id}/starred-by",
    ):
        assert (await author.get(path)).status_code in (404, 405)

    # And no response body anywhere leaks a user id alongside the count.
    detail = (await author.get(f"/api/notices/{notice_id}")).json()
    assert detail["stars"] == 1
    fan_id = (await fan.get("/api/users/me")).json()["id"]
    assert fan_id not in str(detail)


async def test_starring_does_not_notify_the_author(board_user):
    author = await board_user("author@example.com")
    fan = await board_user("fan@example.com")
    notice_id = (await author.post("/api/notices", json=notice_payload())).json()["id"]
    await fan.put(f"/api/notices/{notice_id}/star")

    # A star is a quiet signal; pinging on it would make the board a slot machine.
    assert (await author.get("/api/notifications")).json() == []


# ---- post of the day -------------------------------------------------------


async def _age_stars(notice_id, hours):
    """Backdate a notice's stars, since there's no API for posting old ones."""
    from sqlalchemy import update

    from app.core.database import AsyncSessionLocal
    from app.models import NoticeStar

    async with AsyncSessionLocal() as session:
        await session.execute(
            update(NoticeStar)
            .where(NoticeStar.notice_id == notice_id)
            .values(created_at=datetime.now(timezone.utc) - timedelta(hours=hours))
        )
        await session.commit()


async def test_post_of_the_day_is_the_most_starred_in_the_window(board_user):
    author = await board_user("author@example.com")
    a = await board_user("a@example.com")
    b = await board_user("b@example.com")

    quiet = (await author.post("/api/notices", json=notice_payload(title="Quiet"))).json()
    loud = (await author.post("/api/notices", json=notice_payload(title="Loud"))).json()

    await a.put(f"/api/notices/{quiet['id']}/star")
    await a.put(f"/api/notices/{loud['id']}/star")
    await b.put(f"/api/notices/{loud['id']}/star")

    r = await author.get("/api/notices/top")
    assert r.status_code == 200
    assert r.json()["title"] == "Loud"
    assert r.json()["stars"] == 2


async def test_post_of_the_day_ignores_stars_older_than_the_window(board_user):
    """A rotating spotlight, not a hall of fame: yesterday's winner steps down."""
    author = await board_user("author@example.com")
    a = await board_user("a@example.com")
    b = await board_user("b@example.com")

    old = (await author.post("/api/notices", json=notice_payload(title="Yesterday"))).json()
    fresh = (await author.post("/api/notices", json=notice_payload(title="Today"))).json()

    await a.put(f"/api/notices/{old['id']}/star")
    await b.put(f"/api/notices/{old['id']}/star")
    await _age_stars(old["id"], STAR_WINDOW_HOURS + 2)
    await a.put(f"/api/notices/{fresh['id']}/star")

    r = await author.get("/api/notices/top")
    # "Yesterday" still has more stars all-time, but none of them are recent.
    assert r.json()["title"] == "Today"
    assert (await author.get(f"/api/notices/{old['id']}")).json()["stars"] == 2


async def test_post_of_the_day_is_null_when_nothing_was_starred(board_user):
    author = await board_user("author@example.com")
    await author.post("/api/notices", json=notice_payload())
    r = await author.get("/api/notices/top")
    assert r.status_code == 200
    assert r.json() is None


async def test_post_of_the_day_respects_blocks(board_user):
    author = await board_user("author@example.com")
    fan = await board_user("fan@example.com")
    reader = await board_user("reader@example.com")
    notice_id = (await author.post("/api/notices", json=notice_payload())).json()["id"]
    await fan.put(f"/api/notices/{notice_id}/star")

    author_id = (await author.get("/api/users/me")).json()["id"]
    await reader.post("/api/blocks", json={"blocked_id": author_id})

    assert (await reader.get("/api/notices/top")).json() is None


# ---- the official section --------------------------------------------------


async def test_official_narrows_to_verified_organizations(board_user, make_org, community_id):
    person = await board_user("person@example.com", "Ada")
    await person.post("/api/notices", json=notice_payload(title="A neighbour's post"))

    library = await make_org("library@brooklyn.gov", "Sunset Park Library")
    await library.patch("/api/profiles/me", json={"community_id": community_id})
    await library.post(
        "/api/notices",
        json=notice_payload(category="announcement", title="An official notice"),
    )

    everything = (await person.get("/api/notices")).json()
    assert len(everything) == 2

    official = (await person.get("/api/notices?official=true")).json()
    assert [n["title"] for n in official] == ["An official notice"]
    assert official[0]["author_verified"] is True


# ---- private inquiries toggle ----------------------------------------------


async def test_an_author_can_close_replies(board_user):
    author = await board_user("author@example.com")
    reader = await board_user("reader@example.com")
    notice_id = (
        await author.post(
            "/api/notices", json=notice_payload(allow_direct_inquiries=False)
        )
    ).json()["id"]

    assert (
        await reader.get(f"/api/notices/{notice_id}")
    ).json()["allow_direct_inquiries"] is False

    r = await reader.post(f"/api/notices/{notice_id}/replies", json={"body": "Hello?"})
    assert r.status_code == 403
    assert "replies" in r.json()["message"].lower()


async def test_replies_are_open_by_default(board_user):
    author = await board_user("author@example.com")
    reader = await board_user("reader@example.com")
    notice_id = (await author.post("/api/notices", json=notice_payload())).json()["id"]

    assert (
        await reader.get(f"/api/notices/{notice_id}")
    ).json()["allow_direct_inquiries"] is True
    r = await reader.post(f"/api/notices/{notice_id}/replies", json={"body": "Yes please"})
    assert r.status_code == 201, r.text


async def test_closing_replies_after_the_fact_stops_new_ones(board_user):
    author = await board_user("author@example.com")
    early = await board_user("early@example.com")
    late = await board_user("late@example.com")
    notice_id = (await author.post("/api/notices", json=notice_payload())).json()["id"]

    assert (
        await early.post(f"/api/notices/{notice_id}/replies", json={"body": "First!"})
    ).status_code == 201
    await author.patch(f"/api/notices/{notice_id}", json={"allow_direct_inquiries": False})

    assert (
        await late.post(f"/api/notices/{notice_id}/replies", json={"body": "Too late"})
    ).status_code == 403
    # The reply already given is still readable by the author.
    assert len((await author.get(f"/api/notices/{notice_id}/replies")).json()) == 1


# ---- map pins --------------------------------------------------------------


async def test_a_notice_can_carry_a_map_pin(board_user):
    author = await board_user("author@example.com")
    r = await author.post(
        "/api/notices",
        json=notice_payload(
            category="lost_found", title="Lost: grey cat", location=SUNSET_PARK
        ),
    )
    assert r.status_code == 201, r.text
    loc = r.json()["location"]
    assert abs(loc["lat"] - SUNSET_PARK["lat"]) < 1e-6
    assert abs(loc["lng"] - SUNSET_PARK["lng"]) < 1e-6


async def test_notices_without_a_pin_have_no_location(board_user):
    author = await board_user("author@example.com")
    r = await author.post("/api/notices", json=notice_payload())
    assert r.json()["location"] is None


async def test_the_map_endpoint_returns_only_pinned_notices_nearby(board_user):
    author = await board_user("author@example.com")
    await author.post("/api/notices", json=notice_payload(title="Unpinned"))
    await author.post(
        "/api/notices", json=notice_payload(title="Pinned here", location=SUNSET_PARK)
    )
    await author.post(
        "/api/notices",
        json=notice_payload(
            title="Pinned far away", location={"lat": 40.9, "lng": -73.7}
        ),
    )

    r = await author.get(
        f"/api/notices/map?lat={SUNSET_PARK['lat']}&lng={SUNSET_PARK['lng']}&radius_m=2000"
    )
    assert r.status_code == 200, r.text
    assert [n["title"] for n in r.json()] == ["Pinned here"]


async def test_the_map_endpoint_hides_blocked_authors(board_user):
    author = await board_user("author@example.com")
    reader = await board_user("reader@example.com")
    await author.post(
        "/api/notices", json=notice_payload(title="Pinned", location=SUNSET_PARK)
    )
    author_id = (await author.get("/api/users/me")).json()["id"]
    await reader.post("/api/blocks", json={"blocked_id": author_id})

    r = await reader.get(
        f"/api/notices/map?lat={SUNSET_PARK['lat']}&lng={SUNSET_PARK['lng']}&radius_m=2000"
    )
    assert r.json() == []


async def test_a_pin_can_be_moved_and_removed(board_user):
    author = await board_user("author@example.com")
    notice_id = (
        await author.post("/api/notices", json=notice_payload(location=SUNSET_PARK))
    ).json()["id"]

    moved = {"lat": 40.6600, "lng": -74.0100}
    r = await author.patch(f"/api/notices/{notice_id}", json={"location": moved})
    assert abs(r.json()["location"]["lat"] - moved["lat"]) < 1e-6

    # clear_location is an explicit flag: a null "location" in a PATCH is
    # indistinguishable from "field not sent".
    r = await author.patch(f"/api/notices/{notice_id}", json={"clear_location": True})
    assert r.json()["location"] is None


# ---- expiry windows --------------------------------------------------------


async def test_the_ceiling_is_three_months(board_user):
    author = await board_user("author@example.com")
    assert MAX_EXPIRY_DAYS == 90
    far = datetime.now(timezone.utc) + timedelta(days=400)
    r = await author.post(
        "/api/notices", json=notice_payload(expires_at=far.isoformat())
    )
    expires = datetime.fromisoformat(r.json()["expires_at"])
    assert expires <= datetime.now(timezone.utc) + timedelta(days=90, minutes=1)


async def test_an_author_can_choose_a_shorter_window(board_user):
    author = await board_user("author@example.com")
    soon = datetime.now(timezone.utc) + timedelta(days=7)
    r = await author.post(
        "/api/notices", json=notice_payload(expires_at=soon.isoformat())
    )
    expires = datetime.fromisoformat(r.json()["expires_at"])
    assert abs((expires - soon).total_seconds()) < 60


async def test_meta_advertises_the_expiry_choices(board_user):
    author = await board_user("author@example.com")
    meta = (await author.get("/api/notices/meta")).json()
    assert meta["default_expiry_days"] == DEFAULT_EXPIRY_DAYS
    assert 90 in meta["expiry_choices_days"]
    assert meta["max_body_chars"] >= 8000
