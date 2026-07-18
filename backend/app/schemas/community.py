import uuid

from pydantic import BaseModel, Field

from app.schemas.common import LatLng

# node/way/relation followed by a numeric id. Enforced because this value is
# interpolated into an Overpass query — the pattern blocks injection.
OSM_REF_PATTERN = r"^(node|way|relation)/\d+$"


class CommunityRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    center: LatLng | None
    osm_ref: str | None = None


class CommunityCandidate(BaseModel):
    """A neighborhood suggestion fetched live from OpenStreetMap. It is NOT a
    row in our database yet — it only becomes one (getting an id) when a user
    selects it and we materialize it via POST /api/communities."""

    name: str
    center: LatLng
    osm_ref: str = Field(pattern=OSM_REF_PATTERN)


class CommunityCreate(BaseModel):
    """Materialize a candidate into a real community row (find-or-create).
    Only the OSM reference is trusted from the client — the name and center
    are re-fetched from OpenStreetMap so a caller can't invent a community."""

    osm_ref: str = Field(pattern=OSM_REF_PATTERN)
