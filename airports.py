import json
from pathlib import Path
from typing import Dict, Any, Optional

# In-memory index of airports keyed by IATA code
AIRPORT_INDEX: Dict[str, Dict[str, Any]] = {}


def load_airports() -> None:
    """
    Load airports.json into memory.

    Expected format (built by build_airports_json.py):

      {
        "DTW": {"lat": 42.212, "lon": -83.353, "name": "DETROIT METRO"},
        "ATL": {"lat": 33.6407, "lon": -84.4277, "name": "ATLANTA HARTSFIELD"},
        ...
      }
    """
    global AIRPORT_INDEX

    path = Path(__file__).with_name("airports.json")
    if not path.exists():
        print(f"[airports] airports.json not found at {path}, airport lookup disabled")
        AIRPORT_INDEX = {}
        return

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            AIRPORT_INDEX = data
            print(f"[airports] Loaded {len(AIRPORT_INDEX)} airports from {path}")
        else:
            print(f"[airports] Invalid airports.json structure at {path}")
            AIRPORT_INDEX = {}
    except Exception as e:
        print(f"[airports] Error loading airports.json from {path}: {e}")
        AIRPORT_INDEX = {}


def lookup_airport(code: str) -> Optional[Dict[str, Any]]:
    """
    Return airport record by IATA code (case-insensitive).

    Example record:
      {"lat": 42.212, "lon": -83.353, "name": "DETROIT METRO WAYNE COUNTY"}

    Returns None if not found or if airports.json failed to load.
    """
    if not code:
        return None
    if not AIRPORT_INDEX:
        # Not loaded or failed to load
        return None

    return AIRPORT_INDEX.get(code.strip().upper())
