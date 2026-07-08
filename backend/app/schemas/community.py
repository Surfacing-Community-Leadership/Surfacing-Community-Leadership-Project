import uuid

from pydantic import BaseModel

from app.schemas.common import LatLng


class CommunityRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    center: LatLng | None
