import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import settings
from flights import (
    Flight,
    get_flights,
    get_current_center,
    get_radius_km,
)
from airports import load_airports, lookup_airport

app = FastAPI(title="FlightWall Web")

# Load airports data at startup
load_airports()

# Serve static assets (CSS, JS, logos, etc.)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=FileResponse)
async def index():
    """
    Serve the main HTML page.
    """
    return FileResponse("static/index.html")


class ConfigResponse(BaseModel):
    center_lat: float
    center_lon: float
    radius_km: float
    center_label: Optional[str] = None


@app.get("/api/config", response_model=ConfigResponse)
async def api_get_config():
    """
    Return the default center and radius.

    This is used as an initial seed for each client; actual per-user
    center is maintained entirely on the frontend.
    """
    center_lat, center_lon = get_current_center()
    radius_km = get_radius_km()

    # Prefer explicit label (env or settings) over lat/lon text
    label: Optional[str] = None

    env_label = os.getenv("FLIGHTWALL_CENTER_LABEL")
    if env_label and env_label.strip():
        label = env_label.strip()
    else:
        settings_label = getattr(settings, "center_label", None)
        if isinstance(settings_label, str) and settings_label.strip():
            label = settings_label.strip()

    if not label:
        label = f"{center_lat:.3f}, {center_lon:.3f}"

    return ConfigResponse(
        center_lat=center_lat,
        center_lon=center_lon,
        radius_km=radius_km,
        center_label=label,
    )


@app.get("/api/flights", response_model=List[Flight])
async def api_flights(
    radius_nm: Optional[float] = None,
    center_lat: Optional[float] = None,
    center_lon: Optional[float] = None,
):
    """
    Return the list of flights around the requested center.

    Query params:
      - radius_nm (optional): radius in NM, per user
      - center_lat / center_lon (optional): center point per user;
        if omitted, backend falls back to default center.
    """
    flights = await get_flights(
        center_lat=center_lat,
        center_lon=center_lon,
        radius_nm=radius_nm,
    )
    return flights


class CenterByAirport(BaseModel):
    airport: str  # IATA or local code, e.g. "DTW", "ATL", "Y47"


class CenterResponse(BaseModel):
    center_lat: float
    center_lon: float
    name: Optional[str] = None
    code: Optional[str] = None
    center_label: Optional[str] = None
    elev_ft: Optional[float] = None  # field elevation in feet (MSL)


@app.post("/api/center/airport", response_model=CenterResponse)
async def api_set_center_airport(payload: CenterByAirport):
    """
    Resolve an airport code into a center lat/lon + display label +
    field elevation.

    NOTE: This does not mutate any global state; the frontend is
    responsible for storing/using this center per user.
    """
    rec = lookup_airport(payload.airport)
    if not rec:
        raise HTTPException(status_code=404, detail="Unknown airport code")

    lat = rec.get("lat")
    lon = rec.get("lon")

    if lat is None or lon is None:
        raise HTTPException(
            status_code=500,
            detail="Airport record missing coordinates",
        )

    code = (payload.airport or "").strip().upper()
    name = rec.get("name") or ""
    label = f"{code} – {name}" if name else code

    # Elevation: support multiple possible key names and types.
    elev_ft: Optional[float] = None
    for key in ("elev_ft", "ELEV", "elev", "Elev", "ELEV_FT", "elevation", "ELEVATION"):
        raw = rec.get(key)
        if raw is None:
            continue

        if isinstance(raw, (int, float)):
            elev_ft = float(raw)
            break

        if isinstance(raw, str):
            s = raw.strip()
            if not s:
                continue
            try:
                elev_ft = float(s)
                break
            except ValueError:
                continue

    # Optional: log once for debugging; comment out later if noisy
    print(
        f"airport={code} name={name!r} lat={lat} lon={lon} elev_ft={elev_ft}"
    )

    return CenterResponse(
        center_lat=float(lat),
        center_lon=float(lon),
        name=name,
        code=code,
        center_label=label,
        elev_ft=elev_ft,
    )
