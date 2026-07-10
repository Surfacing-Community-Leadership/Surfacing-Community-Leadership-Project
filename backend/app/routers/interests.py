from fastapi import APIRouter
from sqlalchemy import select

from app.models import Interest
from app.routers.deps import DB
from app.schemas.interest import InterestRead

router = APIRouter(prefix="/api/interests", tags=["interests"])


@router.get("", response_model=list[InterestRead])
async def list_interests(db: DB):
    return (await db.scalars(select(Interest).order_by(Interest.name))).all()
