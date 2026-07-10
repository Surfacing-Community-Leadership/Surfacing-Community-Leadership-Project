import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Block, Community, Interest, Profile, User, user_interests
from app.routers.deps import DB, CurrentUser
from app.schemas.profile import InterestIds, ProfilePublic, ProfileRead, ProfileUpdate

router = APIRouter(prefix="/api/profiles", tags=["profiles"])

AVATAR_DIR = Path("media/avatars")
AVATAR_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
MAX_AVATAR_BYTES = 2 * 1024 * 1024


async def _my_profile(db: AsyncSession, user: User) -> Profile:
    profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.get("/me", response_model=ProfileRead)
async def read_my_profile(db: DB, user: CurrentUser):
    return await _my_profile(db, user)


@router.patch("/me", response_model=ProfileRead)
async def update_my_profile(payload: ProfileUpdate, db: DB, user: CurrentUser):
    profile = await _my_profile(db, user)
    updates = payload.model_dump(exclude_unset=True)

    if "community_id" in updates and updates["community_id"] is not None:
        community = await db.get(Community, updates["community_id"])
        if community is None:
            raise HTTPException(status_code=422, detail="Unknown community")

    for field, value in updates.items():
        setattr(profile, field, value)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.post("/me/avatar", response_model=ProfileRead)
async def upload_avatar(db: DB, user: CurrentUser, file: UploadFile):
    """Stores the image on local disk under media/avatars and points
    avatar_key at it. (Production would use object storage instead.)"""
    ext = AVATAR_TYPES.get(file.content_type)
    if ext is None:
        raise HTTPException(status_code=422, detail="Avatar must be JPEG, PNG or WebP")
    data = await file.read()
    if len(data) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=422, detail="Avatar must be under 2 MB")

    profile = await _my_profile(db, user)
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    for old in AVATAR_DIR.glob(f"{user.id}.*"):  # replacing, not accumulating
        old.unlink()
    (AVATAR_DIR / f"{user.id}.{ext}").write_bytes(data)

    profile.avatar_key = f"avatars/{user.id}.{ext}"
    await db.commit()
    await db.refresh(profile)
    return profile


@router.get("", response_model=list[ProfilePublic])
async def search_profiles(
    db: DB,
    user: CurrentUser,
    q: Annotated[str, Query(min_length=2, max_length=80)],
):
    """Find neighbors by display name. Excludes yourself and anyone with a
    block in either direction."""
    # Escape LIKE wildcards so a search for "100%" means the literal text.
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    i_blocked = select(Block.blocked_id).where(Block.blocker_id == user.id)
    blocked_me = select(Block.blocker_id).where(Block.blocked_id == user.id)

    profiles = (
        await db.scalars(
            select(Profile)
            .where(Profile.display_name.ilike(f"%{escaped}%"))
            .where(Profile.user_id != user.id)
            .where(Profile.user_id.not_in(i_blocked))
            .where(Profile.user_id.not_in(blocked_me))
            .order_by(Profile.display_name)
            .limit(20)
        )
    ).all()
    return profiles


@router.get("/me/interests", response_model=InterestIds)
async def read_my_interests(db: DB, user: CurrentUser):
    ids = (
        await db.scalars(
            select(user_interests.c.interest_id).where(
                user_interests.c.user_id == user.id
            )
        )
    ).all()
    return InterestIds(interest_ids=ids)


@router.put("/me/interests", response_model=InterestIds)
async def replace_my_interests(payload: InterestIds, db: DB, user: CurrentUser):
    unique_ids = list(set(payload.interest_ids))
    if unique_ids:
        found = await db.scalar(
            select(func.count()).select_from(Interest).where(Interest.id.in_(unique_ids))
        )
        if found != len(unique_ids):
            raise HTTPException(status_code=422, detail="Unknown interest id")

    # Replace-all semantics: PUT swaps the full set in one transaction.
    await db.execute(delete(user_interests).where(user_interests.c.user_id == user.id))
    if unique_ids:
        await db.execute(
            user_interests.insert(),
            [{"user_id": user.id, "interest_id": iid} for iid in unique_ids],
        )
    await db.commit()
    return InterestIds(interest_ids=unique_ids)


@router.get("/{user_id}", response_model=ProfilePublic)
async def read_public_profile(user_id: uuid.UUID, db: DB, user: CurrentUser):
    profile = await db.scalar(select(Profile).where(Profile.user_id == user_id))
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile
