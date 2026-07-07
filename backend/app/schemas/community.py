from pydantic import BaseModel
from uuid import UUID


class CommunityResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    center: dict | None  # GeoJSON representation of the GEOGRAPHY(POINT) column
