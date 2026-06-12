"""US state/city geo lookups for the radius-based region builder.

Backed by data/uscities.csv (SimpleMaps Basic v1.79, CC-BY 4.0 — see
data/uscities-LICENSE.txt). The CSV ships with the repo; loaded lazily and
cached in-process on first call.
"""

import csv
import math
import re
import unicodedata
from pathlib import Path

CSV_PATH = Path(__file__).parent.parent / "data" / "uscities.csv"

# Funcheap covers SF + surrounding metro; ~75mi captures San Jose / Santa Cruz / Napa.
SF_LAT, SF_LNG = 37.7749, -122.4194
BAY_AREA_RADIUS_MI = 75

_rows: list[dict] | None = None  # full dataset, normalized
_bay_area_names: set[str] | None = None  # CA city names (lowercase) within radius of SF


def _load():
    """Read the CSV once. Each row: {name, name_lower, state_id, state_name, lat, lng}."""
    global _rows
    if _rows is not None:
        return _rows

    out = []
    with CSV_PATH.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                lat = float(row["lat"])
                lng = float(row["lng"])
            except (TypeError, ValueError):
                continue
            name = row["city"].strip()
            state_id = row["state_id"].strip().upper()
            out.append({
                "name": name,
                "name_lower": name.lower(),
                "state_id": state_id,
                "state_name": row["state_name"].strip(),
                "lat": lat,
                "lng": lng,
            })
    _rows = out
    return _rows


def list_states():
    """Sorted list of [{id, name}] for every US state present in the dataset."""
    seen = {}
    for row in _load():
        seen.setdefault(row["state_id"], row["state_name"])
    return [{"id": sid, "name": name} for sid, name in sorted(seen.items(), key=lambda kv: kv[1])]


def list_cities(state_id):
    """Sorted list of [{name, lat, lng}] for a given state. Deduped by name."""
    state_id = (state_id or "").strip().upper()
    if not state_id:
        return []
    seen = set()
    cities = []
    for row in _load():
        if row["state_id"] != state_id or row["name"] in seen:
            continue
        seen.add(row["name"])
        cities.append({"name": row["name"], "lat": row["lat"], "lng": row["lng"]})
    cities.sort(key=lambda c: c["name"].lower())
    return cities


def cities_within_radius(state_id, city_name, radius_mi, cap=25):
    """Cities in `state_id` within `radius_mi` of `city_name`, nearest first.

    Returns up to `cap` rows: [{name, distance_mi}]. The seed city is always
    first (distance 0). Returns [] if the seed city isn't found in the state.
    """
    state_id = (state_id or "").strip().upper()
    city_name = (city_name or "").strip().lower()
    if not state_id or not city_name:
        return []

    rows = _load()
    seed = next(
        (r for r in rows if r["state_id"] == state_id and r["name_lower"] == city_name),
        None,
    )
    if seed is None:
        return []

    nearby = []
    for r in rows:
        if r["state_id"] != state_id:
            continue
        d = _haversine_miles(seed["lat"], seed["lng"], r["lat"], r["lng"])
        if d <= radius_mi:
            nearby.append({"name": r["name"], "distance_mi": round(d, 1)})

    # Dedupe by name (keep the closest if duplicates exist)
    by_name = {}
    for c in nearby:
        prev = by_name.get(c["name"])
        if prev is None or c["distance_mi"] < prev["distance_mi"]:
            by_name[c["name"]] = c
    nearby = list(by_name.values())

    nearby.sort(key=lambda c: c["distance_mi"])
    return nearby[:cap]


def is_bay_area_city(state_id, city_name):
    """True if the given CA city sits within BAY_AREA_RADIUS_MI of San Francisco."""
    if (state_id or "").strip().lower() != "ca":
        return False
    name = (city_name or "").strip().lower()
    if not name:
        return False
    return name in _bay_area_set()


def _bay_area_set():
    """Lazy-built set of CA city names within radius of SF (lowercase, deduped)."""
    global _bay_area_names
    if _bay_area_names is not None:
        return _bay_area_names
    names = set()
    for r in _load():
        if r["state_id"] != "CA":
            continue
        if _haversine_miles(SF_LAT, SF_LNG, r["lat"], r["lng"]) <= BAY_AREA_RADIUS_MI:
            names.add(r["name_lower"])
    _bay_area_names = names
    return _bay_area_names


def slugify(name):
    """Lowercase, strip accents, drop punctuation, collapse whitespace to '-'."""
    if not name:
        return ""
    # Strip accents
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Drop anything that isn't alphanumeric, space, or hyphen
    cleaned = re.sub(r"[^a-zA-Z0-9\s-]", "", ascii_only).strip().lower()
    # Collapse runs of whitespace/hyphens into single hyphen
    return re.sub(r"[\s-]+", "-", cleaned)


def _haversine_miles(lat1, lng1, lat2, lng2):
    """Great-circle distance in statute miles."""
    R_MI = 3958.7613
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return 2 * R_MI * math.asin(math.sqrt(a))
