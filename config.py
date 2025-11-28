import os
from pydantic import BaseModel

class Settings(BaseModel):
    # Where you are and how far to look (km)
    center_lat: float = float(os.getenv("FLIGHTWALL_CENTER_LAT", "42.2123"))
    center_lon: float = float(os.getenv("FLIGHTWALL_CENTER_LON", "-83.3534"))
    radius_km: float = float(os.getenv("FLIGHTWALL_RADIUS_KM", "130"))

    # ADS-B style source (airplanes.live / ADSBexchange-compatible)
    adsb_api_key: str | None = os.getenv("FLIGHTWALL_ADSB_API_KEY")
    adsb_base_url: str = os.getenv(
        "FLIGHTWALL_ADSB_BASE_URL",
        "https://api.airplanes.live/v2",
    )

    # Route lookup using adsbdb.com (free, no key)
    adsbdb_base_url: str = os.getenv(
        "FLIGHTWALL_ADSBDB_BASE_URL",
        "https://api.adsbdb.com/v0",
    )
    route_lookup_enabled: bool = os.getenv(
        "FLIGHTWALL_ROUTE_LOOKUP",
        "true",
    ).lower() == "true"
    route_max_new_per_cycle: int = int(
        os.getenv("FLIGHTWALL_ROUTE_MAX_NEW_PER_CYCLE", "2")
    )

settings = Settings()

