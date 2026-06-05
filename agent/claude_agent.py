import json
import re
import subprocess
import time
from datetime import date, timedelta
from agent.search import fetch_raw_events, format_for_claude

SYSTEM_PROMPT = """You are a Bay Area event discovery assistant for a family with young children in the South Bay / East Bay.

Given raw event listings, return a JSON object with the best upcoming events and day-trip routes.

GEOGRAPHY — include any Bay Area event; prefer these cities:
- East Bay: Fremont, Union City, Newark, Hayward, San Leandro, Castro Valley, Milpitas
- Tri-Valley: Pleasanton, Livermore, Dublin, San Ramon
- South Bay: San Jose, Santa Clara, Campbell, Cupertino, Los Gatos, Saratoga, Sunnyvale
- Peninsula: Mountain View, Palo Alto, Menlo Park, Redwood City, San Mateo, Burlingame, Foster City
- Coastal & Far: Half Moon Bay, Santa Cruz, Monterey

TIMEFRAME — only include events within:
- Weekdays Mon–Thu: 4pm–11pm
- Friday: 2pm–11pm
- Saturday & Sunday: anytime

RANKING PRIORITIES (most → least important):
1. Free or low-cost
2. Family-friendly / suitable for young children
3. City-sponsored (movies in the park, festivals, fairs, book sales, community events)
4. Outdoor / nature
5. Popular / well-attended

OUTPUT — respond with ONLY valid JSON, no markdown fences, no commentary:
{
  "events": [
    {
      "name": "concise name (Mon Jun 9)",
      "city": "City name",
      "fee": "Free" or "$X",
      "popularity": <1-10>,
      "family_friendly": "Yes" | "No" | "Maybe",
      "link": "https://...",
      "blurb": "one sentence about the event"
    }
  ],
  "routes": [
    {
      "name": "Route title",
      "region": "Region name",
      "date": "Sat Jun 7",
      "stops": [
        {"event": "event name", "time": "10am", "city": "City"},
        {"event": "event name", "time": "2pm",  "city": "City"}
      ],
      "why": "One sentence on why this combo works."
    }
  ]
}

Return all qualifying events ranked by priority. Include 2–3 routes.
"""

# ── Output cache (1-hour TTL) ─────────────────────────────────────────────────
_output_cache: dict = {"data": None, "ts": 0.0}
OUTPUT_CACHE_TTL = 3600


def _prefilter_events(events, max_events=40):
    today = date.today()
    cutoff = today + timedelta(weeks=3)

    in_window = []
    for e in events:
        start = e.get("start_date", "")
        if start:
            try:
                ev_date = date.fromisoformat(start[:10])
                if today <= ev_date <= cutoff:
                    in_window.append(e)
            except ValueError:
                pass
        else:
            in_window.append(e)

    def score(e):
        text = (e.get("title", "") + " " + e.get("description", "")).lower()
        pts = 0
        if "free"     in text: pts += 3
        if "family"   in text: pts += 2
        if "kids"     in text or "children" in text: pts += 2
        if "festival" in text or "fair"     in text: pts += 1
        if e.get("source") == "Funcheap":            pts += 1
        return pts

    in_window.sort(key=score, reverse=True)
    return in_window[:max_events]


def _extract_json(raw):
    # Strip markdown fences if Claude wraps it anyway
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
    return json.loads(cleaned)


def get_events_json():
    """Return cached JSON dict of events + routes, calling Claude only when stale."""
    if _output_cache["data"] is not None and (time.time() - _output_cache["ts"]) < OUTPUT_CACHE_TTL:
        return _output_cache["data"]

    events, today, friday, saturday, sunday = fetch_raw_events()
    events = _prefilter_events(events)
    user_message = format_for_claude(events, today, friday, saturday, sunday)
    prompt = f"{SYSTEM_PROMPT}\n\n---\n\n{user_message}"

    result = subprocess.run(
        ["claude", "-p", prompt],
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr)

    data = _extract_json(result.stdout)

    _output_cache["data"] = data
    _output_cache["ts"] = time.time()
    return data


# Keep run_agent for email_digest.py (returns markdown via old prompt)
def run_agent():
    data = get_events_json()
    events = data.get("events", [])
    routes = data.get("routes", [])

    lines = ["## Events Table\n"]
    lines.append("| Event Name | City | Fee | Popularity (1-10) | Family Friendly | Link |")
    lines.append("|---|---|---|---|---|---|")
    for e in events:
        lines.append(
            f"| {e['name']} | {e['city']} | {e['fee']} "
            f"| {e['popularity']} | {e['family_friendly']} | [Link]({e['link']}) |"
        )

    lines.append("\n## Suggested Day-Trip Routes\n")
    for r in routes:
        lines.append(f"**{r['name']} ({r['region']}) — {r['date']}**")
        for i, s in enumerate(r.get("stops", []), 1):
            lines.append(f"- Stop {i}: {s['event']} — {s['time']} — {s['city']}")
        lines.append(f"\n{r.get('why', '')}\n")

    return "\n".join(lines)
