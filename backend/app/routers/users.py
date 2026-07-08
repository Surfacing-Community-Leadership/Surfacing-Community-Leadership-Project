from fastapi import APIRouter

from app.routers.deps import DB, CurrentUser
from app.schemas.auth import UserMe

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserMe)
async def read_me(user: CurrentUser):
    return user


@router.delete("/me", status_code=204)
async def delete_me(user: CurrentUser, db: DB) -> None:
    # Hard delete by design: profile, connections, blocks, participations and
    # messages cascade away; hosted events survive with host_id set to NULL.
    await db.delete(user)
    await db.commit()
