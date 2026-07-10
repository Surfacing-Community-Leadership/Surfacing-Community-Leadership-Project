"""Helpers for converting between API lat/lng and PostGIS geography values."""

from geoalchemy2 import WKBElement
from geoalchemy2.shape import to_shape

from app.schemas.common import LatLng


def wkt_point(lat: float, lng: float) -> str:
    # PostGIS expects x (longitude) before y (latitude).
    return f"SRID=4326;POINT({lng} {lat})"


def to_latlng(wkb: WKBElement | None) -> LatLng | None:
    if wkb is None:
        return None
    point = to_shape(wkb)
    return LatLng(lat=point.y, lng=point.x)
