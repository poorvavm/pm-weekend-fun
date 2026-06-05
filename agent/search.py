import html
import json
import re
import time
import requests
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# Cities grouped by geography — drives both search and trip routing
CITY_GROUPS = {
    "East Bay": [
        "Fremont", "Union City", "Newark", "Hayward",
        "San Leandro", "Castro Valley", "Milpitas",
    ],
    "Tri-Valley": ["Pleasanton", "Livermore", "Dublin", "San Ramon"],
    "South Bay": [
        "San Jose", "Santa Clara", "Campbell", "Cupertino",
        "Los Gatos", "Saratoga", "Sunnyvale",
    ],
    "Peninsula": [
        "Mountain View", "Los Altos", "Palo Alto", "Menlo Park",
        "Redwood City", "San Carlos", "Belmont", "Foster City",
        "Millbrae", "Burlingame", "San Mateo", "Atherton",
    ],
    "Coastal & Far": ["Half Moon Bay", "Santa Cruz", "Monterey", "Sacramento"],
}

# Eventbrite URL slug per city (lowercase, hyphenated)
EVENTBRITE_CITY_SLUGS = [
    "fremont", "milpitas", "hayward", "san-leandro", "newark",
    "pleasanton", "livermore", "dublin", "san-ramon",
    "san-jose", "santa-clara", "campbell", "cupertino", "sunnyvale",
    "mountain-view", "palo-alto", "menlo-park", "redwood-city",
    "san-mateo", "burlingame", "foster-city",
    "half-moon-bay", "santa-cruz",
]


def get_weekend_dates():
    today = date.today()
    days_until_saturday = (5 - today.weekday()) % 7
    if days_until_saturday == 0:
        days_until_saturday = 7
    saturday = today + timedelta(days=days_until_saturday)
    sunday = saturday + timedelta(days=1)
    friday = saturday - timedelta(days=1)
    return today, friday, saturday, sunday


# ── Eventbrite scraper ────────────────────────────────────────────────────────

def _scrape_eventbrite_city(city_slug):
    url = f"https://www.eventbrite.com/d/ca--{city_slug}/free--events--this-weekend/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    events = []

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
        except (json.JSONDecodeError, TypeError):
            continue

        if isinstance(data, list):
            continue
        items = data.get("itemListElement", [])
        for item in items:
            ev = item.get("item", {})
            if ev.get("@type") != "Event":
                continue
            loc = ev.get("location", {})
            addr = loc.get("address", {})
            events.append({
                "title": ev.get("name", "").strip(),
                "link": ev.get("url", "").strip(),
                "description": ev.get("description", "").strip()[:400],
                "start_date": ev.get("startDate", ""),
                "city": addr.get("addressLocality", city_slug.replace("-", " ").title()),
                "address": addr.get("streetAddress", ""),
                "source": "Eventbrite",
            })

    return events


def _scrape_all_eventbrite():
    all_events = []
    seen_urls = set()
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_scrape_eventbrite_city, slug): slug for slug in EVENTBRITE_CITY_SLUGS}
        for future in as_completed(futures):
            for ev in future.result():
                if ev["link"] not in seen_urls:
                    seen_urls.add(ev["link"])
                    all_events.append(ev)
    return all_events


# ── Funcheap RSS scraper ──────────────────────────────────────────────────────

def _scrape_funcheap(pages=2):
    events = []
    for page in range(1, pages + 1):
        url = f"https://sf.funcheap.com/feed/?paged={page}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            root = ET.fromstring(r.text)
        except Exception:
            continue

        channel = root.find("channel")
        if not channel:
            continue

        for item in channel.findall("item"):
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            description = item.findtext("description", "").strip()
            categories = [c.text for c in item.findall("category") if c.text]

            clean_desc = html.unescape(re.sub(r"<[^>]+>", "", description))[:400]

            events.append({
                "title": title,
                "link": link,
                "description": clean_desc,
                "start_date": "",
                "city": "Bay Area (SF)",
                "address": "",
                "categories": categories,
                "source": "Funcheap",
            })

    return events


# ── Cache (2-hour TTL) ────────────────────────────────────────────────────────

_cache: dict = {"events": None, "ts": 0.0}
CACHE_TTL = 7200  # seconds


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_raw_events():
    today, friday, saturday, sunday = get_weekend_dates()

    if _cache["events"] is not None and (time.time() - _cache["ts"]) < CACHE_TTL:
        return _cache["events"], today, friday, saturday, sunday

    eventbrite_events = _scrape_all_eventbrite()
    funcheap_events = _scrape_funcheap(pages=2)
    all_events = eventbrite_events + funcheap_events

    _cache["events"] = all_events
    _cache["ts"] = time.time()

    return all_events, today, friday, saturday, sunday


def format_for_claude(events, today, friday, saturday, sunday):
    city_groups_str = "\n".join(
        f"  {region}: {', '.join(cities)}"
        for region, cities in CITY_GROUPS.items()
    )

    eb = [e for e in events if e["source"] == "Eventbrite"]
    fc = [e for e in events if e["source"] == "Funcheap"]

    lines = [
        f"TODAY: {today.strftime('%A, %B %d, %Y')}",
        f"TIMEFRAME:",
        f"  Weekdays Mon-Thu: 4pm-11pm",
        f"  Friday {friday.strftime('%B %d')}: 2pm-11pm",
        f"  Saturday {saturday.strftime('%B %d')}: anytime",
        f"  Sunday {sunday.strftime('%B %d')}: anytime",
        "",
        "TARGET CITIES (grouped by geography for trip routing):",
        city_groups_str,
        "",
        f"EVENT DATA: {len(eb)} Eventbrite events + {len(fc)} Funcheap listings",
        "=" * 60,
    ]

    for e in events:
        date_str = f"\nDATE: {e['start_date']}" if e.get("start_date") else ""
        city_str = f"\nCITY: {e['city']}" if e.get("city") else ""
        addr_str = f"\nADDRESS: {e['address']}" if e.get("address") else ""
        cats = ", ".join(e.get("categories", [])) if e.get("categories") else ""
        cats_str = f"\nCATEGORIES: {cats}" if cats else ""

        lines.append(
            f"[{e['source']}] {e['title']}"
            f"{date_str}{city_str}{addr_str}{cats_str}"
            f"\nURL: {e['link']}"
            f"\n{e['description']}"
            f"\n---"
        )

    return "\n".join(lines)
