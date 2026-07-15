from pydantic import BaseModel


class GeocodeResult(BaseModel):
    display_name: str  # human-readable address, e.g. "5th Ave, Brooklyn, NY, USA"
    lat: float
    lng: float
