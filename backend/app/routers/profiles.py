import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Community, Interest, Profile, User, user_interests
from app.routers.deps import DB, CurrentUser
from app.schemas.profile import InterestIds, ProfilePublic, ProfileRead, ProfileUpdate

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


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
