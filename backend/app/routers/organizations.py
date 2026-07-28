"""Local organizations: browsing them, and following the ones you care about."""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.models import OrgFollow, Profile, User
from app.routers.deps import DB, CurrentUser, blocked_counterparts, blocked_either_way
from app.schemas.organization import FollowState, OrganizationSummary

router = APIRouter(prefix="/api/organizations", tags=["organizations"])


async def _org_or_404(db, user_id: uuid.UUID) -> Profile:
    profile = await db.scalar(select(Profile).where(Profile.user_id == user_id))
    if profile is None or profile.account_type != "organization":
        raise HTTPException(status_code=404, detail="Organization not found")
    return profile


@router.get("", response_model=list[OrganizationSummary])
async def list_organizations(
    db: DB,
    user: CurrentUser,
    following: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(gt=0, le=100)] = 50,
):
    """Organizations on the platform, verified ones first.

    `following=true` narrows it to the ones you follow — that's the "your
    organizations" list. Blocked accounts are excluded either way.
    """
    my_follows = select(OrgFollow.org_id).where(OrgFollow.follower_id == user.id)

    query = (
        select(Profile, User.org_verified)
        .join(User, User.id == Profile.user_id)
        .where(Profile.account_type == "organization")
        .where(Profile.user_id.not_in(blocked_counterparts(user.id)))
        # Verified first, then alphabetical — so vetted institutions lead.
        .order_by(User.org_verified.desc(), Profile.display_name)
        .limit(limit)
    )
    if following is True:
        query = query.where(Profile.user_id.in_(my_follows))
    elif following is False:
        query = query.where(Profile.user_id.not_in(my_follows))

    rows = (await db.execute(query)).all()
    if not rows:
        return []

    org_ids = [profile.user_id for profile, _ in rows]
    followed = set(
        (
            await db.scalars(
                select(OrgFollow.org_id).where(
                    OrgFollow.follower_id == user.id, OrgFollow.org_id.in_(org_ids)
                )
            )
        ).all()
    )
    counts = dict(
        (
            await db.execute(
                select(OrgFollow.org_id, func.count())
                .where(OrgFollow.org_id.in_(org_ids))
                .group_by(OrgFollow.org_id)
            )
        ).all()
    )

    return [
        OrganizationSummary(
            user_id=profile.user_id,
            display_name=profile.display_name,
            avatar_key=profile.avatar_key,
            bio=profile.bio,
            org_category=profile.org_category,
            org_website=profile.org_website,
            verified=bool(verified),
            following=profile.user_id in followed,
            followers=counts.get(profile.user_id, 0),
        )
        for profile, verified in rows
    ]


@router.get("/{user_id}/follow", response_model=FollowState)
async def read_follow_state(user_id: uuid.UUID, db: DB, user: CurrentUser):
    await _org_or_404(db, user_id)
    following = await db.scalar(
        select(OrgFollow.id).where(
            OrgFollow.follower_id == user.id, OrgFollow.org_id == user_id
        )
    )
    followers = await db.scalar(
        select(func.count()).select_from(OrgFollow).where(OrgFollow.org_id == user_id)
    )
    return FollowState(following=following is not None, followers=followers or 0)


@router.put("/{user_id}/follow", response_model=FollowState)
async def follow_organization(user_id: uuid.UUID, db: DB, user: CurrentUser):
    """Follow an organization. Idempotent — following twice is not an error."""
    await _org_or_404(db, user_id)
    if user_id == user.id:
        raise HTTPException(status_code=409, detail="You cannot follow yourself")
    if await blocked_either_way(db, user.id, user_id):
        raise HTTPException(status_code=403, detail="You cannot follow this account")

    existing = await db.scalar(
        select(OrgFollow.id).where(
            OrgFollow.follower_id == user.id, OrgFollow.org_id == user_id
        )
    )
    if existing is None:
        db.add(OrgFollow(follower_id=user.id, org_id=user_id))
        await db.commit()

    followers = await db.scalar(
        select(func.count()).select_from(OrgFollow).where(OrgFollow.org_id == user_id)
    )
    return FollowState(following=True, followers=followers or 0)


@router.delete("/{user_id}/follow", response_model=FollowState)
async def unfollow_organization(user_id: uuid.UUID, db: DB, user: CurrentUser):
    """Stop following. Also idempotent, so an accidental double-tap is fine."""
    await _org_or_404(db, user_id)
    follow = await db.scalar(
        select(OrgFollow).where(
            OrgFollow.follower_id == user.id, OrgFollow.org_id == user_id
        )
    )
    if follow is not None:
        await db.delete(follow)
        await db.commit()

    followers = await db.scalar(
        select(func.count()).select_from(OrgFollow).where(OrgFollow.org_id == user_id)
    )
    return FollowState(following=False, followers=followers or 0)
