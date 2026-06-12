"""City configuration — loaded from data/config.json, edited via /config UI."""

import json
import os
import re
import tempfile
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "data" / "config.json"
SLUG_PATTERN = re.compile(r"^[a-z0-9-]+$")
STATE_PATTERN = re.compile(r"^[a-z]{2}$")
DEFAULT_STATE = "ca"
PERSONA_MAX_LEN = 1000
DEFAULT_PREFERENCES = {"persona": ""}

DEFAULT_CONFIG = {
    "regions": [
        {
            "name": "East Bay",
            "enabled": True,
            "state": "ca",
            "cities": [
                {"name": "Fremont",       "slug": "fremont"},
                {"name": "Union City",    "slug": "union-city"},
                {"name": "Newark",        "slug": "newark"},
                {"name": "Hayward",       "slug": "hayward"},
                {"name": "San Leandro",   "slug": "san-leandro"},
                {"name": "Castro Valley", "slug": ""},
                {"name": "Milpitas",      "slug": "milpitas"},
            ],
        },
        {
            "name": "Tri-Valley",
            "enabled": True,
            "state": "ca",
            "cities": [
                {"name": "Pleasanton", "slug": "pleasanton"},
                {"name": "Livermore",  "slug": "livermore"},
                {"name": "Dublin",     "slug": "dublin"},
                {"name": "San Ramon",  "slug": "san-ramon"},
            ],
        },
        {
            "name": "South Bay",
            "enabled": True,
            "state": "ca",
            "cities": [
                {"name": "San Jose",     "slug": "san-jose"},
                {"name": "Santa Clara",  "slug": "santa-clara"},
                {"name": "Campbell",     "slug": "campbell"},
                {"name": "Cupertino",    "slug": "cupertino"},
                {"name": "Los Gatos",    "slug": ""},
                {"name": "Saratoga",     "slug": ""},
                {"name": "Sunnyvale",    "slug": "sunnyvale"},
            ],
        },
        {
            "name": "Peninsula",
            "enabled": True,
            "state": "ca",
            "cities": [
                {"name": "Mountain View", "slug": "mountain-view"},
                {"name": "Los Altos",     "slug": ""},
                {"name": "Palo Alto",     "slug": "palo-alto"},
                {"name": "Menlo Park",    "slug": "menlo-park"},
                {"name": "Redwood City",  "slug": "redwood-city"},
                {"name": "San Carlos",    "slug": ""},
                {"name": "Belmont",       "slug": ""},
                {"name": "Foster City",   "slug": "foster-city"},
                {"name": "Millbrae",      "slug": ""},
                {"name": "Burlingame",    "slug": "burlingame"},
                {"name": "San Mateo",     "slug": "san-mateo"},
                {"name": "Atherton",      "slug": ""},
            ],
        },
        {
            "name": "Coastal & Far",
            "enabled": True,
            "state": "ca",
            "cities": [
                {"name": "Half Moon Bay", "slug": "half-moon-bay"},
                {"name": "Santa Cruz",    "slug": "santa-cruz"},
                {"name": "Monterey",      "slug": ""},
                {"name": "Sacramento",    "slug": ""},
            ],
        },
    ],
    "preferences": {
        "persona": "",
    },
}

_cache: dict | None = None


def validate(cfg):
    """Raise ValueError if cfg is malformed. Returns the cfg on success."""
    if not isinstance(cfg, dict) or not isinstance(cfg.get("regions"), list):
        raise ValueError("Config must be an object with a 'regions' array.")

    for r_idx, region in enumerate(cfg["regions"]):
        if not isinstance(region, dict):
            raise ValueError(f"Region #{r_idx + 1} must be an object.")
        name = (region.get("name") or "").strip()
        if not name:
            raise ValueError(f"Region #{r_idx + 1} is missing a name.")
        if "enabled" in region and not isinstance(region["enabled"], bool):
            raise ValueError(f"Region '{name}' has non-boolean 'enabled' value.")
        if "state" in region:
            state = (region.get("state") or "").strip().lower()
            if state and not STATE_PATTERN.match(state):
                raise ValueError(
                    f"Region '{name}' has invalid state '{region['state']}' "
                    f"(must be a 2-letter US state code, e.g. 'ca')."
                )
        if not isinstance(region.get("cities"), list):
            raise ValueError(f"Region '{name}' must have a 'cities' array.")

        for c_idx, city in enumerate(region["cities"]):
            if not isinstance(city, dict):
                raise ValueError(f"City #{c_idx + 1} in '{name}' must be an object.")
            cname = (city.get("name") or "").strip()
            if not cname:
                raise ValueError(f"City #{c_idx + 1} in '{name}' is missing a name.")
            slug = (city.get("slug") or "").strip()
            if slug and not SLUG_PATTERN.match(slug):
                raise ValueError(
                    f"City '{cname}' in '{name}' has invalid slug '{slug}' "
                    f"(must be lowercase letters, digits, and hyphens only)."
                )

    if "preferences" in cfg:
        prefs = cfg["preferences"]
        if not isinstance(prefs, dict):
            raise ValueError("Preferences must be an object.")
        if "persona" in prefs:
            if not isinstance(prefs["persona"], str):
                raise ValueError("Preferences 'persona' must be a string.")
            if len(prefs["persona"]) > PERSONA_MAX_LEN:
                raise ValueError(
                    f"Preferences 'persona' is too long ({len(prefs['persona'])} chars; "
                    f"max {PERSONA_MAX_LEN})."
                )
    return cfg


def _normalize(cfg):
    """Trim whitespace on names + slugs; lowercase slugs; fill defaults."""
    out = {"regions": []}
    for region in cfg.get("regions", []):
        state = (region.get("state") or DEFAULT_STATE).strip().lower()
        out["regions"].append({
            "name": region.get("name", "").strip(),
            "enabled": bool(region.get("enabled", True)),
            "state": state,
            "cities": [
                {
                    "name": c.get("name", "").strip(),
                    "slug": c.get("slug", "").strip().lower(),
                }
                for c in region.get("cities", [])
            ],
        })
    prefs_in = cfg.get("preferences") or {}
    out["preferences"] = {
        "persona": str(prefs_in.get("persona", DEFAULT_PREFERENCES["persona"])).strip(),
    }
    return out


def load_config():
    """Return cached config; load from disk (or seed defaults) on first call."""
    global _cache
    if _cache is not None:
        return _cache

    if CONFIG_PATH.exists():
        try:
            with CONFIG_PATH.open() as f:
                cfg = json.load(f)
            validate(cfg)
            _cache = cfg
            return _cache
        except (json.JSONDecodeError, ValueError) as e:
            print(f"[config] {CONFIG_PATH} is invalid ({e}); falling back to defaults.")

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(DEFAULT_CONFIG)
    _cache = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
    return _cache


def save_config(cfg):
    """Validate, persist, refresh cache, and invalidate downstream caches."""
    global _cache
    # Validate BEFORE normalize so type-strict checks (e.g. bool fields) see the
    # raw input, not the coerced version.
    validate(cfg)
    cfg = _normalize(cfg)

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(cfg)
    _cache = cfg

    # Lazy imports to avoid circular deps (search/claude_agent both import this module)
    from agent import search, claude_agent
    search.invalidate_cache()
    claude_agent.invalidate_cache()

    return _cache


def _atomic_write(cfg):
    fd, tmp_path = tempfile.mkstemp(
        prefix=".config-", suffix=".json", dir=str(CONFIG_PATH.parent)
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(cfg, f, indent=2)
        os.replace(tmp_path, CONFIG_PATH)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def get_scrape_targets():
    """List of {state, slug} for enabled regions only — drives the Eventbrite scrape."""
    cfg = load_config()
    return [
        {"state": region.get("state", DEFAULT_STATE), "slug": c["slug"]}
        for region in cfg["regions"]
        if region.get("enabled", True)
        for c in region["cities"]
        if c.get("slug")
    ]


def get_city_groups():
    """Ordered mapping of region name -> city display names, enabled regions only."""
    cfg = load_config()
    return {
        region["name"]: [c["name"] for c in region["cities"]]
        for region in cfg["regions"]
        if region.get("enabled", True)
    }


def get_preferences():
    """User preferences dict with defaults filled in for missing fields."""
    prefs = load_config().get("preferences") or {}
    return {
        "persona": str(prefs.get("persona", DEFAULT_PREFERENCES["persona"])).strip(),
    }


def get_persona():
    return get_preferences()["persona"]


def is_funcheap_enabled():
    """Auto-on iff any enabled region has at least one Bay Area city (within
    ~75mi of SF). Funcheap is SF-specific, so it's only useful in that case."""
    from agent import geo  # lazy import to avoid circular deps at module load
    cfg = load_config()
    for region in cfg["regions"]:
        if not region.get("enabled", True):
            continue
        state = region.get("state", DEFAULT_STATE)
        for c in region["cities"]:
            if geo.is_bay_area_city(state, c.get("name", "")):
                return True
    return False
