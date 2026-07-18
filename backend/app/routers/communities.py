"""Communities: the neighborhoods a user can belong to.

The catalog is sourced *dynamically* from OpenStreetMap rather than a fixed
seed list. The flow has two steps that keep an external source compatible with
our relational model:

  1. GET /nearby  — proxy the Overpass API for `place` nodes around a point.
     These are *candidates*: name + center + a stable OSM ref. No DB writes.
  2. POST ""      — "materialize" a chosen candidate into a real row
     (find-or-create by osm_ref), minting the UUID that profiles/events use.

So the `communities` table is a lazily-grown cache of neighborhoods people
actually joined — we never mirror all of OSM. See docs/DECISIONS.md.
"""

import math
import re
import time
import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.geo import to_latlng, wkt_point
from app.models import Community
from app.routers.deps import DB, CurrentUser
from app.schemas.common import LatLng
from app.schemas.community import CommunityCandidate, CommunityCreate, CommunityRead

router = APIRouter(prefix="/api/communities", tags=["communities"])

# Overpass is a read API over OpenStreetMap data. We ask for `place` nodes of
# neighborhood-ish granularity within a radius of the user. Proxied server-side
# for the same reasons as geocoding: identifying User-Agent + swappable source.
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "OursApp/0.1 (neighborhood community MVP)"
PLACE_KINDS = "neighbourhood|suburb|quarter|borough"
DEFAULT_RADIUS_M = 3000
MAX_RADIUS_M = 30000
MAX_CANDIDATES = 40

# Short-lived cache of candidates handed out by /nearby, keyed by osm_ref:
#   osm_ref -> (expires_at_monotonic, name, lat, lng)
# It exists so that materialize (POST) doesn't have to hit Overpass a second
# time for a neighborhood the user just saw — the public Overpass service
# rate-limits hard, and a second live call at save time is exactly where we
# don't want flakiness. The values still originate from OSM (via /nearby), so
# the client can't forge them. In-memory and per-process, so a cold cache
# (restart, cache miss, expiry) falls back to a live OSM lookup by id.
CANDIDATE_TTL_S = 1800  # 30 minutes
_candidate_cache: dict[str, tuple[float, str, float, float]] = {}


def _cache_put(osm_ref: str, name: str, lat: float, lng: float) -> None:
    now = time.monotonic()
    if len(_candidate_cache) > 2000:  # opportunistic prune of expired entries
        for stale in [k for k, v in _candidate_cache.items() if v[0] < now]:
            del _candidate_cache[stale]
    _candidate_cache[osm_ref] = (now + CANDIDATE_TTL_S, name, lat, lng)


def _cache_get(osm_ref: str) -> tuple[str, float, float] | None:
    entry = _candidate_cache.get(osm_ref)
    if entry is None:
        return None
    expires, name, lat, lng = entry
    if expires < time.monotonic():
        _candidate_cache.pop(osm_ref, None)
        return None
    return name, lat, lng


def _serialize(community: Community) -> CommunityRead:
    return CommunityRead(
        id=community.id,
        name=community.name,
        slug=community.slug,
        center=to_latlng(community.center),
        osm_ref=community.osm_ref,
    )


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "community"


def _dist2(lat: float, lng: float, lat0: float, lng0: float) -> float:
    """Cheap squared planar distance, good enough for *sorting* nearby points.
    Longitude is scaled by cos(latitude) so degrees are comparable on both
    axes. We don't need real meters here — just a consistent ordering."""
    dlat = lat - lat0
    dlng = (lng - lng0) * math.cos(math.radians(lat0))
    return dlat * dlat + dlng * dlng


async def _overpass(query: str) -> list[dict]:
    """Run an Overpass QL query and return its elements. Raises httpx.HTTPError
    on transport/HTTP failure and ValueError on a malformed body — callers
    decide whether to degrade (nearby) or surface an error (materialize)."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            OVERPASS_URL, data={"data": query}, headers={"User-Agent": USER_AGENT}
        )
        resp.raise_for_status()
        return resp.json().get("elements", [])


@router.get("", response_model=list[CommunityRead])
async def list_communities(db: DB):
    communities = (await db.scalars(select(Community).order_by(Community.name))).all()
    return [_serialize(c) for c in communities]


@router.get("/nearby", response_model=list[CommunityCandidate])
async def nearby_communities(
    user: CurrentUser,  # gate the external proxy behind auth
    lat: Annotated[float, Query(ge=-90, le=90)],
    lng: Annotated[float, Query(ge=-180, le=180)],
    radius: Annotated[int, Query(ge=200, le=MAX_RADIUS_M)] = DEFAULT_RADIUS_M,
):
    """Live neighborhood suggestions near a point, nearest first. Degrades to
    an empty list if Overpass is slow or down, so onboarding never breaks."""
    query = (
        f"[out:json][timeout:15];"
        f'node(around:{radius},{lat},{lng})["place"~"^({PLACE_KINDS})$"]["name"];'
        f"out body {MAX_CANDIDATES + 20};"
    )
    try:
        elements = await _overpass(query)
    except (httpx.HTTPError, ValueError):
        return []

    # Build candidates, dedupe by name (OSM sometimes has near-duplicates),
    # keeping the closest of each, then sort nearest-first.
    best: dict[str, tuple[float, CommunityCandidate]] = {}
    for el in elements:
        name = el.get("tags", {}).get("name")
        el_lat, el_lng = el.get("lat"), el.get("lon")
        if not name or el_lat is None or el_lng is None:
            continue
        d = _dist2(el_lat, el_lng, lat, lng)
        if name not in best or d < best[name][0]:
            best[name] = (
                d,
                CommunityCandidate(
                    name=name,
                    center=LatLng(lat=el_lat, lng=el_lng),
                    osm_ref=f"{el['type']}/{el['id']}",
                ),
            )
    ranked = sorted(best.values(), key=lambda pair: pair[0])
    result = [candidate for _, candidate in ranked[:MAX_CANDIDATES]]
    # Remember what we handed out so a follow-up POST can skip a second
    # Overpass call for a neighborhood the user just saw.
    for c in result:
        _cache_put(c.osm_ref, c.name, c.center.lat, c.center.lng)
    return result


@router.post("", response_model=CommunityRead)
async def materialize_community(payload: CommunityCreate, db: DB, user: CurrentUser):
    """Find-or-create a community from an OSM reference. Idempotent per
    osm_ref: two users picking the same neighborhood share one row. The name
    and center come from OpenStreetMap (cache from /nearby, else a live lookup),
    never from the client — so a caller can't invent a community."""
    osm_id = payload.osm_ref.split("/")[1]
    existing = await db.scalar(
        select(Community).where(Community.osm_ref == payload.osm_ref)
    )
    if existing is not None:
        return _serialize(existing)

    # Prefer the value /nearby just cached; only hit Overpass on a cache miss.
    cached = _cache_get(payload.osm_ref)
    if cached is not None:
        name, lat, lng = cached
    else:
        # osm_ref is pattern-validated (node|way|relation)/<digits>, so it is
        # safe to interpolate. Ways/relations have no lat/lon of their own —
        # ask Overpass for a representative center instead.
        el_type = payload.osm_ref.split("/")[0]
        out = "out center 1;" if el_type in ("way", "relation") else "out body 1;"
        try:
            elements = await _overpass(f"{el_type}({osm_id});{out}")
        except (httpx.HTTPError, ValueError):
            raise HTTPException(
                status_code=503, detail="Neighborhood lookup unavailable"
            )
        if not elements:
            raise HTTPException(status_code=404, detail="OSM element not found")
        el = elements[0]
        name = el.get("tags", {}).get("name")
        center = el.get("center", el)  # ways/relations put it under "center"
        lat, lng = center.get("lat"), center.get("lon")
        if not name or lat is None or lng is None:
            raise HTTPException(
                status_code=422, detail="OSM element is not a usable place"
            )

    community = Community(
        name=name,
        slug=f"{_slugify(name)}-{osm_id}",  # osm_ref is unique → slug is too
        osm_ref=payload.osm_ref,
        center=wkt_point(lat, lng),
    )
    db.add(community)
    try:
        await db.commit()
    except IntegrityError:
        # A concurrent request materialized the same osm_ref first — reuse it.
        await db.rollback()
        existing = await db.scalar(
            select(Community).where(Community.osm_ref == payload.osm_ref)
        )
        if existing is None:
            raise
        return _serialize(existing)
    await db.refresh(community)
    return _serialize(community)


@router.get("/{community_id}", response_model=CommunityRead)
async def read_community(community_id: uuid.UUID, db: DB):
    community = await db.get(Community, community_id)
    if community is None:
        raise HTTPException(status_code=404, detail="Community not found")
    return _serialize(community)
