"""Address search (geocoding), proxied to OpenStreetMap's Nominatim service.

Why proxy through our backend instead of calling Nominatim from the browser:
  - Nominatim's usage policy requires a User-Agent identifying the app; a
    browser can't set that reliably, but the server can.
  - It keeps the provider swappable (Photon, Mapbox, ...) behind one stable
    endpoint — the frontend never learns which service we use.
  - It's the natural place to add caching or rate limiting later.

Nominatim etiquette we honor: an identifying User-Agent, few requests (the
frontend debounces so we don't query per keystroke), and a short timeout.
If this ever grows heavy, self-host Nominatim or move to Photon/Mapbox.
"""

from typing import Annotated

import httpx
from fastapi import APIRouter, Query

from app.routers.deps import CurrentUser
from app.schemas.geocode import GeocodeResult

router = APIRouter(prefix="/api/geocode", tags=["geocode"])

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "OursApp/0.1 (neighborhood community MVP)"


@router.get("", response_model=list[GeocodeResult])
async def geocode(
    user: CurrentUser,  # gate the proxy behind auth; only signed-in users search
    q: Annotated[str, Query(min_length=3, max_length=200)],
):
    params = {"q": q, "format": "jsonv2", "limit": 5, "addressdetails": 0}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                NOMINATIM_URL, params=params, headers={"User-Agent": USER_AGENT}
            )
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError):
        # Upstream down, slow, or malformed — degrade to "no suggestions"
        # rather than failing the whole create-event page.
        return []

    return [
        GeocodeResult(
            display_name=item["display_name"],
            lat=float(item["lat"]),
            lng=float(item["lon"]),  # Nominatim calls it "lon"; our API says "lng"
        )
        for item in data
    ]
