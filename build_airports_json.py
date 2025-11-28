import csv
import json
from pathlib import Path


def build_airports_json(csv_path: Path, json_path: Path) -> None:
    """
    Convert a FAA-style airports CSV into a compact JSON mapping like:

      {
        "DTW": {"lat": 42.212, "lon": -83.353, "name": "Detroit Metro"},
        "ATL": {"lat": 33.6407, "lon": -84.4277, "name": "Atlanta Intl"},
        ...
      }

    Expected CSV columns:
      - ARPT_ID      (IATA code, e.g. DTW)
      - ARPT_NAME    (airport name)
      - LAT_DECIMAL  (latitude in decimal degrees)
      - LONG_DECIMAL (longitude in decimal degrees)
    """
    airports = {}

    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            code = (row.get("ARPT_ID") or "").strip().upper()
            name = (row.get("ARPT_NAME") or "").strip()

            lat_val = row.get("LAT_DECIMAL") or ""
            lon_val = row.get("LONG_DECIMAL") or ""

            # Skip rows without a code
            if not code:
                continue

            try:
                lat = float(lat_val)
                lon = float(lon_val)
            except (TypeError, ValueError):
                # Bad / missing coordinates, skip
                continue

            airports[code] = {
                "lat": lat,
                "lon": lon,
                "name": name,
            }

    json_path.write_text(json.dumps(airports), encoding="utf-8")
    print(f"Wrote {len(airports)} airport codes to {json_path}")


if __name__ == "__main__":
    base = Path(__file__).parent
    csv_file = base / "airports_raw.csv"   # adjust name if needed
    json_file = base / "airports.json"

    build_airports_json(csv_file, json_file)
