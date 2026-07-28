"""The neighborhood notice board.

Scoped by community, not by radius: everyone in a neighborhood reads the same
board, which is what makes it a *place* rather than a personalized feed. See
app.core.notices for the three rules that keep it quiet (expiry, an allowance,
a closed category list) and for why there is no crime-and-safety category.

Posting requires a confirmed email address. That is the only spam gate the board
has, and it costs an attacker a working inbox per throwaway account.
"""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import and_, func, select

from app.core.notices import (
    MAX_LIVE_NOTICES,
    categories_for,
    default_expires_at,
    is_category_allowed,
    latest_expires_at,
)
from app.core.notifications import notify
from app.models import Community, Notice, NoticeReply, Profile, User
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
)

router = APIRouter(prefix="/api/notices", tags=["notices"])

NO_COMMUNITY = "Choose your neighborhood to use the board"
UNCONFIRMED_EMAIL = "Confirm your email address to post a notice"
ALLOWANCE_FULL = f"You already have {MAX_LIVE_NOTICES} notices up"


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


def _summary(
    notice: Notice,
    author_name: str | None,
    account_type: str | None,
    org_verified: bool | None,
    *,
    is_mine: bool,
    reply_count: int | None = None,
    i_replied: bool = False,
) -> NoticeSummary:
    return NoticeSummary(
        id=notice.id,
        category=notice.category,
        title=notice.title,
        body=notice.body,
        place_hint=notice.place_hint,
        author_id=notice.author_id,
        author_name=author_name,
        author_is_org=account_type == "organization",
        # The badge only means something on an organization account.
        author_verified=bool(org_verified) and account_type == "organization",
        expires_at=notice.expires_at,
        resolved=notice.resolved_at is not None,
        created_at=notice.created_at,
        # Reply counts are the author's business alone: showing "4 replies" to
        # everyone would leak who is interested in what.
        reply_count=reply_count if is_mine else None,
        i_replied=i_replied,
    )


async def _get_notice_for_viewer(db, notice_id: uuid.UUID, user: User) -> Notice:
    """A notice the viewer is allowed to see: on their own board, and not from
    someone they have a block with. 404 rather than 403 throughout, so probing
    ids never confirms one exists."""
    notice = await db.get(Notice, notice_id)
    if notice is None:
        raise HTTPException(status_code=404, detail="Notice not found")
    if notice.author_id == user.id:
        return notice
    if await get_my_community_id(db, user.id) != notice.community_id:
        raise HTTPException(status_code=404, detail="Notice not found")
    if await blocked_either_way(db, user.id, notice.author_id):
        raise HTTPException(status_code=404, detail="Notice not found")
    return notice


# Declared before /{notice_id} so "meta" isn't parsed as a UUID path param.
@router.get("/meta", response_model=BoardMeta)
async def read_board_meta(db: DB, user: CurrentUser):
    """Everything the board screen needs before it can render: which
    neighborhood it is, what this account may post, and what's left of the
    allowance. Never errors on a missing neighborhood — it reports the reason so
    the UI can show the picker instead of an error."""
    now = datetime.now(timezone.utc)
    community_id = await get_my_community_id(db, user.id)
    account_type = await get_account_type(db, user.id)
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
    elif live >= MAX_LIVE_NOTICES:
        reason = ALLOWANCE_FULL
    else:
        reason = None

    return BoardMeta(
        community_id=community_id,
        community_name=community_name,
        categories=list(categories_for(account_type)),
        live_count=live,
        max_live=MAX_LIVE_NOTICES,
        can_post=reason is None,
        blocked_reason=reason,
    )


@router.get("", response_model=list[NoticeSummary])
async def list_notices(
    db: DB,
    user: CurrentUser,
    category: Annotated[str | None, Query()] = None,
    mine: Annotated[bool, Query()] = False,
    include_resolved: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(gt=0, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """The board, newest first.

    `mine=true` returns your own notices whatever their state, since you need to
    see an expired one to manage it. Otherwise: your neighborhood's live
    notices, minus anyone you have a block with.
    """
    now = datetime.now(timezone.utc)
    community_id = await get_my_community_id(db, user.id)
    # No neighborhood means no board. Empty rather than an error: /meta already
    # told the client why, and it renders the picker.
    if community_id is None and not mine:
        return []

    query = (
        select(Notice, Profile.display_name, Profile.account_type, User.org_verified)
        .outerjoin(Profile, Profile.user_id == Notice.author_id)
        .outerjoin(User, User.id == Notice.author_id)
        .order_by(Notice.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    if mine:
        query = query.where(Notice.author_id == user.id)
    else:
        query = (
            query.where(Notice.community_id == community_id)
            .where(Notice.author_id.not_in(blocked_counterparts(user.id)))
            .where(Notice.expires_at > now)
        )
        if not include_resolved:
            query = query.where(Notice.resolved_at.is_(None))

    if category is not None:
        query = query.where(Notice.category == category)

    rows = (await db.execute(query)).all()
    if not rows:
        return []

    notice_ids = [notice.id for notice, *_ in rows]
    # One round trip for the author's own reply counts, and one for "have I
    # already replied to this" — rather than a query per row.
    my_notice_ids = [n.id for n, *_ in rows if n.author_id == user.id]
    counts: dict[uuid.UUID, int] = {}
    if my_notice_ids:
        counts = dict(
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
            reply_count=counts.get(notice.id, 0),
            i_replied=notice.id in replied,
        )
        for notice, name, account_type, verified in rows
    ]


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
            detail="That category is for verified organization accounts",
        )

    if await _live_count(db, user.id, now) >= MAX_LIVE_NOTICES:
        raise HTTPException(status_code=409, detail=ALLOWANCE_FULL)

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
    is_mine = notice.author_id == user.id
    reply_count = (
        await db.scalar(
            select(func.count())
            .select_from(NoticeReply)
            .where(NoticeReply.notice_id == notice.id)
        )
        or 0
    )
    i_replied = (
        await db.scalar(
            select(NoticeReply.id).where(
                NoticeReply.notice_id == notice.id, NoticeReply.author_id == user.id
            )
        )
    ) is not None
    return _summary(
        notice,
        name,
        account_type,
        verified,
        is_mine=is_mine,
        reply_count=reply_count,
        i_replied=i_replied,
    )


@router.patch("/{notice_id}", response_model=NoticeSummary)
async def update_notice(
    notice_id: uuid.UUID, payload: NoticeUpdate, db: DB, user: CurrentUser
):
    """Edit your own notice, extend it, or mark it done. The category is fixed
    after posting — changing it would rewrite what neighbors already replied to."""
    now = datetime.now(timezone.utc)
    notice = await db.get(Notice, notice_id)
    if notice is None:
        raise HTTPException(status_code=404, detail="Notice not found")
    if notice.author_id != user.id:
        raise HTTPException(status_code=403, detail="That isn't your notice")

    updates = payload.model_dump(exclude_unset=True)
    resolved = updates.pop("resolved", None)

    # Checked before anything is mutated: putting a notice back on the board
    # spends allowance, and the guard has to run while the row still counts as
    # resolved.
    if resolved is False and notice.resolved_at is not None:
        if await _live_count(db, user.id, now) >= MAX_LIVE_NOTICES:
            raise HTTPException(status_code=409, detail=ALLOWANCE_FULL)

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
    reply_count = (
        await db.scalar(
            select(func.count())
            .select_from(NoticeReply)
            .where(NoticeReply.notice_id == notice.id)
        )
        or 0
    )
    return _summary(
        notice,
        profile.display_name if profile else None,
        profile.account_type if profile else None,
        user.org_verified,
        is_mine=True,
        reply_count=reply_count,
    )


@router.delete("/{notice_id}", status_code=204)
async def delete_notice(notice_id: uuid.UUID, db: DB, user: CurrentUser) -> None:
    notice = await db.get(Notice, notice_id)
    if notice is None:
        raise HTTPException(status_code=404, detail="Notice not found")
    if notice.author_id != user.id:
        raise HTTPException(status_code=403, detail="That isn't your notice")
    await db.delete(notice)
    await db.commit()


@router.get("/{notice_id}/replies", response_model=list[NoticeReplyRead])
async def list_replies(notice_id: uuid.UUID, db: DB, user: CurrentUser):
    """Only the author reads the replies to a notice. This is the whole reason
    the board has no comment threads: an answer goes to one person."""
    notice = await db.get(Notice, notice_id)
    if notice is None:
        raise HTTPException(status_code=404, detail="Notice not found")
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
        raise HTTPException(status_code=409, detail="That's your own notice")
    if notice.resolved_at is not None or notice.expires_at <= now:
        raise HTTPException(status_code=409, detail="That notice is closed")

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
