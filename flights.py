import os
import httpx
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2, degrees
from typing import List, Dict, Tuple, Optional
from pydantic import BaseModel

from config import settings

# ---------------------------------------------------------------------
# Default center & radius (from env/settings)
# ---------------------------------------------------------------------


def get_current_center() -> Tuple[float, float]:
    """
    Default center (lat, lon) from env variables or settings.
    This is now only a fallback; actual center is per-user and
    passed in from the client.
    """
    center_lat = float(
        os.getenv("FLIGHTWALL_CENTER_LAT", getattr(settings, "center_lat", 0.0))
    )
    center_lon = float(
        os.getenv("FLIGHTWALL_CENTER_LON", getattr(settings, "center_lon", 0.0))
    )
    return center_lat, center_lon


def get_radius_km() -> float:
    """
    Default radius in kilometers, derived from env or settings.
    Used as a fallback if the client does not supply radius_nm.
    """
    return float(
        os.getenv("FLIGHTWALL_RADIUS_KM", getattr(settings, "radius_km", 200.0))
    )


# ---------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------


def haversine(lat1, lon1, lat2, lon2):
    """Calculate distance (km) between two lat/lon points."""
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


def bearing(lat1, lon1, lat2, lon2):
    """Calculate bearing (degrees) from point A to B."""
    dlon = radians(lon2 - lon1)
    x = sin(dlon) * cos(radians(lat2))
    y = cos(radians(lat1)) * sin(radians(lat2)) - sin(radians(lat1)) * cos(
        radians(lat2)
    ) * cos(dlon)
    b = atan2(x, y)
    return (degrees(b) + 360) % 360


# ---------------------------------------------------------------------
# Airline lookup
# ---------------------------------------------------------------------


AIRLINE_PREFIXES: Dict[str, str] = {
    "DAL": "Delta",
    "AAL": "American",
    "UAL": "United",
    "SWA": "Southwest",
    "JBU": "JetBlue",
    "NKS": "Spirit",
    "FFT": "Frontier",
    "ASA": "Alaska",
    "RPA": "Republic",
    "SKW": "SkyWest",
    "ENY": "Envoy",
    "GJS": "GoJet",
    "EJA": "NetJets",
    "EJM": "Executive Jet Management",
    "UPS": "UPS",
    "FDX": "FedEx",
    "JIA": "PSA",
    "PDT": "Piedmont",
    "CPZ": "Compass",
    "N": "GA Aircraft",
    "EDV": "Endeavor",
    "CJT": "CargoJet",
}


def get_airline_from_callsign(callsign: str) -> Optional[str]:
    """
    Determine airline name from callsign prefix.
    Example:
      DAL2968 -> Delta
      UAL1525 -> United
      N447MM  -> GA Aircraft
    """
    if not callsign:
        return None

    cs = callsign.strip().upper()

    # US N-number
    if cs.startswith("N") and len(cs) >= 2 and cs[1].isalnum():
        return AIRLINE_PREFIXES.get("N")

    prefix = ""
    for ch in cs:
        if ch.isalpha():
            prefix += ch
        else:
            break
        if len(prefix) == 3:
            break

    if not prefix:
        return None

    return AIRLINE_PREFIXES.get(prefix)


# ---------------------------------------------------------------------
# Aircraft type lookup
# ---------------------------------------------------------------------


def get_aircraft_type(ac: dict) -> Optional[str]:
    """Try multiple possible keys for aircraft type."""
    for key in ("t", "type", "icao_type", "mdl"):
        val = ac.get(key)
        if isinstance(val, str):
            val = val.strip()
            if val and val.lower() != "adsb_icao":
                return val
    return None


# ---------------------------------------------------------------------
# Flight model
# ---------------------------------------------------------------------


class Flight(BaseModel):
    callsign: str
    airline: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    aircraft_type: Optional[str] = None
    altitude_ft: Optional[int] = None
    distance_km: Optional[float] = None
    bearing_deg: Optional[float] = None
    gs: Optional[float] = None          # ground speed (knots) from ADS-B "gs"
    baro_rate: Optional[int] = None     # vertical speed (fpm) from ADS-B "baro_rate"
    updated_at: datetime


# ---------------------------------------------------------------------
# Route lookup cache
# ---------------------------------------------------------------------

route_cache: Dict[str, Tuple[Optional[str], Optional[str]]] = {}


async def enrich_routes_adsbdb(flights: List[Flight]) -> None:
    """Fill in origin/destination via adsbdb.com (free API)."""
    if not getattr(settings, "route_lookup_enabled", False):
        return

    max_new = getattr(settings, "route_max_new_per_cycle", 2)
    new_count = 0

    async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
        for f in flights:
            if f.origin or f.destination:
                continue

            cs = (f.callsign or "").strip().upper()
            if not cs:
                continue

            # Cached
            if cs in route_cache:
                f.origin, f.destination = route_cache[cs]
                continue

            if new_count >= max_new:
                continue

            url = f"{settings.adsbdb_base_url}/callsign/{cs}"

            try:
                resp = await client.get(
                    url, headers={"User-Agent": "flightwall-web/0.1"}
                )

                if resp.status_code == 404:
                    route_cache[cs] = (None, None)
                    new_count += 1
                    continue

                resp.raise_for_status()
                data = resp.json() or {}
                response = data.get("response") or {}
                fr = response.get("flightroute") or {}

                origin_obj = fr.get("origin") or {}
                dest_obj = fr.get("destination") or {}

                def pick(apt: Optional[dict]) -> Optional[str]:
                    if not isinstance(apt, dict):
                        return None
                    for key in ("icao_code", "iata_code", "name"):
                        val = apt.get(key)
                        if isinstance(val, str) and val.strip():
                            return val.strip()
                    return None

                origin = pick(origin_obj)
                dest = pick(dest_obj)

                f.origin = origin
                f.destination = dest

                route_cache[cs] = (origin, dest)
                new_count += 1

            except Exception as e:
                print("ADSBDB route error for", cs, ":", e)


# ---------------------------------------------------------------------
# Main fetcher (airplanes.live / ADSBexchange compatible)
# ---------------------------------------------------------------------


async def get_flights(
    center_lat: Optional[float] = None,
    center_lon: Optional[float] = None,
    radius_nm: Optional[float] = None,
) -> List[Flight]:
    """
    Fetch aircraft and compute distance/bearing from a given center.

    center_lat/center_lon:
      - If provided, use these coords.
      - If None, fall back to default center from env/settings.

    radius_nm:
      - If provided, use this value (in nautical miles) for the ADS-B query.
      - If None, fall back to configured radius_km from settings/env.
      - Clamped to [10, 250] NM.
    """

    # Determine center
    if center_lat is None or center_lon is None:
        center_lat, center_lon = get_current_center()
    else:
        try:
            center_lat = float(center_lat)
            center_lon = float(center_lon)
        except Exception:
            center_lat, center_lon = get_current_center()

    # Determine radius in NM
    if radius_nm is None:
        radius_km = get_radius_km()
        try:
            radius_nm = float(radius_km) / 1.852
        except Exception:
            radius_nm = 200.0 / 1.852  # fallback
    else:
        try:
            radius_nm = float(radius_nm)
        except Exception:
            radius_km = get_radius_km()
            radius_nm = float(radius_km) / 1.852

    # Clamp to 10–250 NM
    if radius_nm < 10.0:
        radius_nm = 10.0
    if radius_nm > 250.0:
        radius_nm = 250.0

    url = f"{settings.adsb_base_url}/point/{center_lat}/{center_lon}/{radius_nm:.2f}"

    headers = {}
    if getattr(settings, "adsb_api_key", None):
        headers["api-auth"] = settings.adsb_api_key

    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            r = await client.get(url, headers=headers)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        print("ADSB API error:", e)
        return []

    now = datetime.utcnow()
    flights: List[Flight] = []

    aircraft_list = data.get("ac", [])

    for ac in aircraft_list:
        callsign = ac.get("flight") or ac.get("callsign") or None
        if not callsign:
            continue

        lat = ac.get("lat")
        lon = ac.get("lon")
        alt = ac.get("alt_baro")

        # Motion fields from ADS-B
        gs = ac.get("gs")
        baro_rate = ac.get("baro_rate")

        if lat is None or lon is None:
            continue

        # Distance and bearing from our center
        dist = haversine(center_lat, center_lon, lat, lon)
        brg = bearing(center_lat, center_lon, lat, lon)

        flights.append(
            Flight(
                callsign=callsign.strip(),
                airline=get_airline_from_callsign(callsign),
                origin=None,
                destination=None,
                aircraft_type=get_aircraft_type(ac),
                altitude_ft=int(alt) if isinstance(alt, (int, float)) else None,
                distance_km=dist,
                bearing_deg=brg,
                gs=float(gs) if isinstance(gs, (int, float)) else None,
                baro_rate=int(baro_rate) if isinstance(baro_rate, (int, float)) else None,
                updated_at=now,
            )
        )

    # Sort by distance then (descending) altitude
    flights.sort(
        key=lambda f: (
            f.distance_km if f.distance_km is not None else 1e9,
            -(f.altitude_ft or 0),
        )
    )

    await enrich_routes_adsbdb(flights)

    return flights
