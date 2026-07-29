"""The community board.

Called the "community board" in the interface; the table, the routes and the
model are still `notice`/`notices`. That's deliberate — renaming a shipped
schema and its migration chain to match a label change buys nothing and risks
a lot. Read "notice" as "board post" throughout this file.

Reading the board is scoped by community, not by radius: everyone in a
neighborhood reads the same board, which is what makes it a *place* rather than
a personalized feed. See app.core.notices for the rules that keep it quiet
(expiry, an allowance, a closed list of post types) and for why there is no
crime-and-safety type.

Two things here are deliberately narrow, and both matter:

  * **Stars are counted, never listed.** There is no endpoint that reveals who
    starred a post — not to the public and not to its author. A count says
    "this was useful"; a list of names would make it a popularity contest.
  * **Replies are private and optional.** One line, to the author only, and only
    when they left `allow_direct_inquiries` on.

Posting requires a confirmed email. That is the only spam gate the board has,
and it costs an attacker a working inbox per throwaway account.
"""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import and_, func, select

from app.core.geo import to_latlng, wkt_point
from app.core.notices import (
    DEFAULT_EXPIRY_DAYS,
    categories_for,
    default_expires_at,
    is_category_allowed,
    latest_expires_at,
    max_live_for,
    star_window_start,
)
from app.core.notifications import notify
from app.models import Community, Notice, NoticeReply, NoticeStar, Profile, User
from app.routers.deps import (
    DB,
    CurrentUser,
    blocked_counterparts,
    blocked_either_way,
    get_account_type,
    get_my_community_id,
)
from app.schemas.notice import (
    BoardMeta,
    NoticeCreate,
    NoticeReplyCreate,
    NoticeReplyRead,
    NoticeSummary,
    NoticeUpdate,
    StarState,
)

router = APIRouter(prefix="/api/notices", tags=["notices"])

NO_COMMUNITY = "Choose your neighborhood to use the board"
UNCONFIRMED_EMAIL = "Confirm your email address to post on the board"
INQUIRIES_CLOSED = "This post isn't taking replies"


def _live_clause(now: datetime):
    """Still on the board: not expired and not marked done."""
    return and_(Notice.expires_at > now, Notice.resolved_at.is_(None))


async def _live_count(db, author_id: uuid.UUID, now: datetime) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(Notice)
            .where(Notice.author_id == author_id)
            .where(_live_clause(now))
        )
    ) or 0


def _allowance_message(limit: int) -> str:
    return f"You already have {limit} posts up"


def _summary(
    notice: Notice,
    author_name: str | None,
    account_type: str | None,
    org_verified: bool | None,
    *,
    is_mine: bool,
    stars: int = 0,
    i_starred: bool = False,
    reply_count: int | None = None,
    i_replied: bool = False,
) -> NoticeSummary:
    return NoticeSummary(
        id=notice.id,
        category=notice.category,
        title=notice.title,
        body=notice.body,
        place_hint=notice.place_hint,
        location=to_latlng(notice.location),
        author_id=notice.author_id,
        author_name=author_name,
        author_is_org=account_type == "organization",
        # The badge only means something on an organization account.
        author_verified=bool(org_verified) and account_type == "organization",
        allow_direct_inquiries=notice.allow_direct_inquiries,
        expires_at=notice.expires_at,
        resolved=notice.resolved_at is not None,
        created_at=notice.created_at,
        stars=stars,
        i_starred=i_starred,
        # Reply counts are the author's business alone: showing "4 replies" to
        # everyone would leak who is interested in what.
        reply_count=reply_count if is_mine else None,
        i_replied=i_replied,
    )


async def _decorate(db, rows, user: User) -> list[NoticeSummary]:
    """Turn (notice, author_name, account_type, org_verified) rows into
    summaries, attaching star counts and the viewer's own star/reply state in a
    fixed number of queries rather than one per row."""
    if not rows:
        return []

    notice_ids = [notice.id for notice, *_ in rows]
    my_notice_ids = [n.id for n, *_ in rows if n.author_id == user.id]

    star_counts = dict(
        (
            await db.execute(
                select(NoticeStar.notice_id, func.count())
                .where(NoticeStar.notice_id.in_(notice_ids))
                .group_by(NoticeStar.notice_id)
            )
        ).all()
    )
    starred = set(
        (
            await db.scalars(
                select(NoticeStar.notice_id).where(
                    NoticeStar.notice_id.in_(notice_ids),
                    NoticeStar.user_id == user.id,
                )
            )
        ).all()
    )
    reply_counts: dict[uuid.UUID, int] = {}
    if my_notice_ids:
        reply_counts = dict(
            (
                await db.execute(
                    select(NoticeReply.notice_id, func.count())
                    .where(NoticeReply.notice_id.in_(my_notice_ids))
                    .group_by(NoticeReply.notice_id)
                )
            ).all()
        )
    replied = set(
        (
            await db.scalars(
                select(NoticeReply.notice_id).where(
                    NoticeReply.notice_id.in_(notice_ids),
                    NoticeReply.author_id == user.id,
                )
            )
        ).all()
    )

    return [
        _summary(
            notice,
            name,
            account_type,
            verified,
            is_mine=notice.author_id == user.id,
            stars=star_counts.get(notice.id, 0),
            i_starred=notice.id in starred,
            reply_count=reply_counts.get(notice.id, 0),
            i_replied=notice.id in replied,
        )
        for notice, name, account_type, verified in rows
    ]


def _with_author(query):
    """Attach the author's display name, account type and badge to a notice
    query. Every read path needs all three."""
    return query.outerjoin(Profile, Profile.user_id == Notice.author_id).outerjoin(
        User, User.id == Notice.author_id
    )


# "Official" means a vetted institution: an organization account carrying the
# badge. coalesce() rather than a bare comparison because the author joins are
# outer — a NULL from a missing profile must read as "not official", not as NULL
# (which would drop the row from BOTH sides of the split below).
_IS_OFFICIAL = and_(
    func.coalesce(User.org_verified, False).is_(True),
    func.coalesce(Profile.account_type, "person") == "organization",
)

# The board's two reading tabs. Deliberately a complete partition of the board:
# "organizations" is the official side, "posts" is *everything else* rather than
# "people only". An unverified organization (a mutual-aid group on a .org, say)
# therefore shows up under posts instead of falling between the two tabs and
# becoming unreachable.
SOURCES = ("all", "posts", "organizations")


def _apply_source(query, source: str):
    if source == "organizations":
        return query.where(_IS_OFFICIAL)
    if source == "posts":
        return query.where(~_IS_OFFICIAL)
    return query


def _board_query(
    user: User, community_id: uuid.UUID, now: datetime, *, include_resolved: bool = False
):
    """Notices on one neighborhood's board, minus anyone the viewer has a block
    with. The shared spine of the list, the map and post-of-the-day, so those
    three can never disagree about what is visible to whom."""
    query = _with_author(
        select(Notice, Profile.display_name, Profile.account_type, User.org_verified)
    ).where(
        Notice.community_id == community_id,
        Notice.author_id.not_in(blocked_counterparts(user.id)),
        Notice.expires_at > now,
    )
    if not include_resolved:
        query = query.where(Notice.resolved_at.is_(None))
    return query


async def _get_notice_for_viewer(db, notice_id: uuid.UUID, user: User) -> Notice:
    """A notice the viewer is allowed to see: on their own board, and not from
    someone they have a block with. 404 rather than 403 throughout, so probing
    ids never confirms one exists."""
    notice = await db.get(Notice, notice_id)
    if notice is None:
        raise HTTPException(status_code=404, detail="Post not found")
    if notice.author_id == user.id:
        return notice
    if await get_my_community_id(db, user.id) != notice.community_id:
        raise HTTPException(status_code=404, detail="Post not found")
    if await blocked_either_way(db, user.id, notice.author_id):
        raise HTTPException(status_code=404, detail="Post not found")
    return notice


# Declared before /{notice_id} so these aren't parsed as UUID path params.
@router.get("/meta", response_model=BoardMeta)
async def read_board_meta(db: DB, user: CurrentUser):
    """Everything the board screen needs before it can render: which
    neighborhood it is, what this account may post, and what's left of the
    allowance. Never errors on a missing neighborhood — it reports the reason so
    the UI can show the picker instead of an error."""
    now = datetime.now(timezone.utc)
    community_id = await get_my_community_id(db, user.id)
    account_type = await get_account_type(db, user.id)
    limit = max_live_for(account_type)
    community_name = (
        await db.scalar(select(Community.name).where(Community.id == community_id))
        if community_id
        else None
    )
    live = await _live_count(db, user.id, now) if community_id else 0

    if community_id is None:
        reason = NO_COMMUNITY
    elif user.email_confirmed_at is None:
        reason = UNCONFIRMED_EMAIL
    elif live >= limit:
        reason = _allowance_message(limit)
    else:
        reason = None

    return BoardMeta(
        community_id=community_id,
        community_name=community_name,
        categories=list(categories_for(account_type)),
        live_count=live,
        max_live=limit,
        can_post=reason is None,
        blocked_reason=reason,
        default_expiry_days=DEFAULT_EXPIRY_DAYS,
    )


@router.get("/top", response_model=NoticeSummary | None)
async def read_post_of_the_day(db: DB, user: CurrentUser):
    """The notice that earned the most stars in the trailing window.

    Ranked on *recent* stars rather than the all-time count, so this is a
    rotating spotlight and not a hall of fame — a good post from this morning can
    beat last month's most-starred one. Returns null when nothing has been
    starred lately, and the board simply shows no highlight.
    """
    now = datetime.now(timezone.utc)
    community_id = await get_my_community_id(db, user.id)
    if community_id is None:
        return None

    recent = (
        select(NoticeStar.notice_id, func.count().label("recent_stars"))
        .where(NoticeStar.created_at >= star_window_start(now))
        .group_by(NoticeStar.notice_id)
        .subquery()
    )
    row = (
        await db.execute(
            _board_query(user, community_id, now)
            .join(recent, recent.c.notice_id == Notice.id)
            # Ties break toward the newer post, for the same rotating reason.
            .order_by(recent.c.recent_stars.desc(), Notice.created_at.desc())
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    return (await _decorate(db, [row], user))[0]


@router.get("/map", response_model=list[NoticeSummary])
async def list_pinned_notices(
    db: DB,
    user: CurrentUser,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lng: Annotated[float, Query(ge=-180, le=180)],
    radius_m: Annotated[int, Query(gt=0, le=100_000)] = 5000,
    limit: Annotated[int, Query(gt=0, le=200)] = 100,
):
    """Notices that carry a location, for the informational pins on the map.

    Separate from the events map query rather than folded into it: a notice is
    not an event, the two have no common ordering (notices have no start time),
    and keeping them apart means the map's event list can't accidentally fill
    with things nobody can attend.
    """
    now = datetime.now(timezone.utc)
    community_id = await get_my_community_id(db, user.id)
    if community_id is None:
        return []

    point = func.ST_GeogFromText(wkt_point(lat, lng))
    rows = (
        await db.execute(
            _board_query(user, community_id, now)
            .where(Notice.location.isnot(None))
            .where(func.ST_DWithin(Notice.location, point, radius_m))
            .order_by(func.ST_Distance(Notice.location, point))
            .limit(limit)
        )
    ).all()
    return await _decorate(db, rows, user)


@router.get("", response_model=list[NoticeSummary])
async def list_notices(
    db: DB,
    user: CurrentUser,
    category: Annotated[str | None, Query()] = None,
    source: Annotated[str, Query()] = "all",
    mine: Annotated[bool, Query()] = False,
    include_resolved: Annotated[bool, Query()] = False,
    exclude_id: Annotated[uuid.UUID | None, Query()] = None,
    limit: Annotated[int, Query(gt=0, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """The board, newest first.

    `source` picks the reading tab: "posts" for the neighbourhood side,
    "organizations" for posts from verified institutions, "all" for both.
    `mine=true` returns your own posts whatever their state, since you need to
    see an expired one to manage it.

    `exclude_id` drops one post from the results. The board highlights the post
    of the day above the list, and filtering it out client-side would leave that
    page one short — excluding it here keeps every page the same size.
    """
    if source not in SOURCES:
        raise HTTPException(
            status_code=422, detail=f"source must be one of {', '.join(SOURCES)}"
        )
    now = datetime.now(timezone.utc)
    community_id = await get_my_community_id(db, user.id)
    # No neighborhood means no board. Empty rather than an error: /meta already
    # told the client why, and it renders the picker.
    if community_id is None and not mine:
        return []

    if mine:
        query = _with_author(
            select(Notice, Profile.display_name, Profile.account_type, User.org_verified)
        ).where(Notice.author_id == user.id)
    else:
        query = _board_query(
            user, community_id, now, include_resolved=include_resolved
        )

    # "Yours" is your own posts regardless of which side of the board they sit
    # on, so the source split doesn't apply to it.
    if not mine:
        query = _apply_source(query, source)
    if exclude_id is not None:
        query = query.where(Notice.id != exclude_id)
    if category is not None:
        query = query.where(Notice.category == category)

    rows = (
        await db.execute(
            query.order_by(Notice.created_at.desc()).limit(limit).offset(offset)
        )
    ).all()
    return await _decorate(db, rows, user)


@router.post("", response_model=NoticeSummary, status_code=201)
async def create_notice(payload: NoticeCreate, db: DB, user: CurrentUser):
    now = datetime.now(timezone.utc)
    community_id = await get_my_community_id(db, user.id)
    if community_id is None:
        raise HTTPException(status_code=409, detail=NO_COMMUNITY)
    if user.email_confirmed_at is None:
        raise HTTPException(status_code=403, detail=UNCONFIRMED_EMAIL)

    account_type = await get_account_type(db, user.id)
    if not is_category_allowed(account_type, payload.category):
        # Naming the reason: announcements and service changes carry an
        # institution's authority, so they need an organization behind them.
        raise HTTPException(
            status_code=403,
            detail="That post type is for verified organization accounts",
        )

    limit = max_live_for(account_type)
    if await _live_count(db, user.id, now) >= limit:
        raise HTTPException(status_code=409, detail=_allowance_message(limit))

    expires_at = payload.expires_at or default_expires_at(now)
    if expires_at <= now:
        raise HTTPException(status_code=422, detail="expires_at must be in the future")
    # Clamped rather than rejected: an over-long request still posts, just for
    # the maximum window.
    expires_at = min(expires_at, latest_expires_at(now))

    notice = Notice(
        author_id=user.id,
        community_id=community_id,
        category=payload.category,
        title=payload.title,
        body=payload.body,
        place_hint=payload.place_hint,
        location=(
            wkt_point(payload.location.lat, payload.location.lng)
            if payload.location
            else None
        ),
        allow_direct_inquiries=payload.allow_direct_inquiries,
        expires_at=expires_at,
    )
    db.add(notice)
    await db.commit()
    await db.refresh(notice)

    profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    return _summary(
        notice,
        profile.display_name if profile else None,
        account_type,
        user.org_verified,
        is_mine=True,
        reply_count=0,
    )


@router.get("/{notice_id}", response_model=NoticeSummary)
async def read_notice(notice_id: uuid.UUID, db: DB, user: CurrentUser):
    notice = await _get_notice_for_viewer(db, notice_id, user)
    row = (
        await db.execute(
            select(Profile.display_name, Profile.account_type, User.org_verified)
            .select_from(User)
            .outerjoin(Profile, Profile.user_id == User.id)
            .where(User.id == notice.author_id)
        )
    ).first()
    name, account_type, verified = row if row else (None, None, None)
    return (
        await _decorate(db, [(notice, name, account_type, verified)], user)
    )[0]


@router.patch("/{notice_id}", response_model=NoticeSummary)
async def update_notice(
    notice_id: uuid.UUID, payload: NoticeUpdate, db: DB, user: CurrentUser
):
    """Edit your own post: its type, words, whereabouts, pin, expiry, whether it
    takes replies, and whether it's done.

    Everything an author wrote is editable, including the type — a mis-picked
    type is a normal mistake and there's no reason to make someone delete and
    repost to fix it. What is NOT editable is who it belongs to or the fact that
    it exists, and the type is re-checked against the account so a person can't
    relabel their post as an official announcement.
    """
    now = datetime.now(timezone.utc)
    notice = await db.get(Notice, notice_id)
    if notice is None:
        raise HTTPException(status_code=404, detail="Post not found")
    if notice.author_id != user.id:
        raise HTTPException(status_code=403, detail="That isn't your post")

    updates = payload.model_dump(exclude_unset=True)
    resolved = updates.pop("resolved", None)
    clear_location = updates.pop("clear_location", False)
    new_location = updates.pop("location", None)

    new_category = updates.get("category")
    if new_category is not None and not is_category_allowed(
        await get_account_type(db, user.id), new_category
    ):
        raise HTTPException(
            status_code=403,
            detail="That post type is for verified organization accounts",
        )

    # Checked before anything is mutated: putting a notice back on the board
    # spends allowance, and the guard has to run while the row still counts as
    # resolved.
    if resolved is False and notice.resolved_at is not None:
        limit = max_live_for(await get_account_type(db, user.id))
        if await _live_count(db, user.id, now) >= limit:
            raise HTTPException(status_code=409, detail=_allowance_message(limit))

    if "expires_at" in updates and updates["expires_at"] is not None:
        # Re-clamped on every edit, so repeated "extend" presses can't walk a
        # notice forward indefinitely.
        requested = updates["expires_at"]
        if requested <= now:
            raise HTTPException(
                status_code=422, detail="expires_at must be in the future"
            )
        updates["expires_at"] = min(requested, latest_expires_at(now))

    for field, value in updates.items():
        setattr(notice, field, value)

    if clear_location:
        notice.location = None
    elif new_location is not None:
        notice.location = wkt_point(new_location["lat"], new_location["lng"])

    if resolved is True and notice.resolved_at is None:
        notice.resolved_at = now
    elif resolved is False and notice.resolved_at is not None:
        # Putting it back up shouldn't resurrect an expired notice silently, so
        # an already-expired one gets a fresh default window.
        notice.resolved_at = None
        if notice.expires_at <= now:
            notice.expires_at = default_expires_at(now)

    await db.commit()
    await db.refresh(notice)

    profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    return (
        await _decorate(
            db,
            [
                (
                    notice,
                    profile.display_name if profile else None,
                    profile.account_type if profile else None,
                    user.org_verified,
                )
            ],
            user,
        )
    )[0]


@router.delete("/{notice_id}", status_code=204)
async def delete_notice(notice_id: uuid.UUID, db: DB, user: CurrentUser) -> None:
    notice = await db.get(Notice, notice_id)
    if notice is None:
        raise HTTPException(status_code=404, detail="Post not found")
    if notice.author_id != user.id:
        raise HTTPException(status_code=403, detail="That isn't your post")
    await db.delete(notice)
    await db.commit()


# ---- stars -----------------------------------------------------------------
#
# Note what is missing: any way to read the list of people who starred a notice.
# Only the count is exposed, and the author has no privileged view of it either.


async def _star_state(db, notice_id: uuid.UUID, user_id: uuid.UUID) -> StarState:
    stars = (
        await db.scalar(
            select(func.count())
            .select_from(NoticeStar)
            .where(NoticeStar.notice_id == notice_id)
        )
    ) or 0
    mine = await db.scalar(
        select(NoticeStar.id).where(
            NoticeStar.notice_id == notice_id, NoticeStar.user_id == user_id
        )
    )
    return StarState(starred=mine is not None, stars=stars)


@router.put("/{notice_id}/star", response_model=StarState)
async def star_notice(notice_id: uuid.UUID, db: DB, user: CurrentUser):
    """Star a notice. Idempotent, and capped at one per account by a unique
    constraint — starring twice is not an error and does not count twice."""
    notice = await _get_notice_for_viewer(db, notice_id, user)
    existing = await db.scalar(
        select(NoticeStar.id).where(
            NoticeStar.notice_id == notice.id, NoticeStar.user_id == user.id
        )
    )
    if existing is None:
        db.add(NoticeStar(notice_id=notice.id, user_id=user.id))
        await db.commit()
    # No notification: a star is a quiet signal, and "someone starred your post"
    # is exactly the kind of ping that turns a board into a slot machine.
    return await _star_state(db, notice.id, user.id)


@router.delete("/{notice_id}/star", response_model=StarState)
async def unstar_notice(notice_id: uuid.UUID, db: DB, user: CurrentUser):
    """Take a star back. Also idempotent, so a double-tap is fine."""
    notice = await _get_notice_for_viewer(db, notice_id, user)
    star = await db.scalar(
        select(NoticeStar).where(
            NoticeStar.notice_id == notice.id, NoticeStar.user_id == user.id
        )
    )
    if star is not None:
        await db.delete(star)
        await db.commit()
    return await _star_state(db, notice.id, user.id)


# ---- private replies -------------------------------------------------------


@router.get("/{notice_id}/replies", response_model=list[NoticeReplyRead])
async def list_replies(notice_id: uuid.UUID, db: DB, user: CurrentUser):
    """Only the author reads the replies to a notice. This is the whole reason
    the board has no comment threads: an answer goes to one person."""
    notice = await db.get(Notice, notice_id)
    if notice is None:
        raise HTTPException(status_code=404, detail="Post not found")
    if notice.author_id != user.id:
        raise HTTPException(status_code=403, detail="Only the author sees replies")

    rows = (
        await db.execute(
            select(NoticeReply, Profile.display_name)
            .outerjoin(Profile, Profile.user_id == NoticeReply.author_id)
            # A block after the fact hides the reply, same as it hides events.
            .where(NoticeReply.notice_id == notice_id)
            .where(NoticeReply.author_id.not_in(blocked_counterparts(user.id)))
            .order_by(NoticeReply.created_at.desc())
        )
    ).all()
    return [
        NoticeReplyRead(
            id=reply.id,
            author_id=reply.author_id,
            author_name=name,
            body=reply.body,
            created_at=reply.created_at,
        )
        for reply, name in rows
    ]


@router.post("/{notice_id}/replies", response_model=NoticeReplyRead, status_code=201)
async def reply_to_notice(
    notice_id: uuid.UUID, payload: NoticeReplyCreate, db: DB, user: CurrentUser
):
    """Answer a notice privately. Replying twice edits what you said rather than
    adding a second line — the author's inbox stays one message per neighbor."""
    now = datetime.now(timezone.utc)
    notice = await _get_notice_for_viewer(db, notice_id, user)
    if notice.author_id == user.id:
        raise HTTPException(status_code=409, detail="That's your own post")
    if not notice.allow_direct_inquiries:
        raise HTTPException(status_code=403, detail=INQUIRIES_CLOSED)
    if notice.resolved_at is not None or notice.expires_at <= now:
        raise HTTPException(status_code=409, detail="That post is closed")

    reply = await db.scalar(
        select(NoticeReply).where(
            NoticeReply.notice_id == notice_id, NoticeReply.author_id == user.id
        )
    )
    if reply is None:
        reply = NoticeReply(notice_id=notice_id, author_id=user.id, body=payload.body)
        db.add(reply)
        await db.flush()
        # Only a first reply notifies. Editing yours shouldn't ping the author
        # again — that would hand one neighbor an unlimited pinger.
        await notify(
            db,
            user_id=notice.author_id,
            type="notice_reply",
            actor_id=user.id,
            notice_id=notice.id,
        )
    else:
        reply.body = payload.body

    await db.commit()
    await db.refresh(reply)

    name = await db.scalar(select(Profile.display_name).where(Profile.user_id == user.id))
    return NoticeReplyRead(
        id=reply.id,
        author_id=reply.author_id,
        author_name=name,
        body=reply.body,
        created_at=reply.created_at,
    )
