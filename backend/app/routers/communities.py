import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.core.geo import to_latlng
from app.models import Community
from app.routers.deps import DB
from app.schemas.community import CommunityRead

router = APIRouter(prefix="/api/communities", tags=["communities"])


def _serialize(community: Community) -> CommunityRead:
    return CommunityRead(
        id=community.id,
        name=community.name,
        slug=community.slug,
        center=to_latlng(community.center),
    )


@router.get("", response_model=list[CommunityRead])
async def list_communities(db: DB):
    communities = (await db.scalars(select(Community).order_by(Community.name))).all()
    return [_serialize(c) for c in communities]


@router.get("/{community_id}", response_model=CommunityRead)
async def read_community(community_id: uuid.UUID, db: DB):
    community = await db.get(Community, community_id)
    if community is None:
        raise HTTPException(status_code=404, detail="Community not found")
    return _serialize(community)
