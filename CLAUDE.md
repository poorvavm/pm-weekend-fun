# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup (first time)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Run the web app (port 5050)
.venv/bin/python3 app.py

# Send the weekly email digest manually (also what the cron job runs)
.venv/bin/python3 email_digest.py

# Verify the Thursday 8am cron job is installed
crontab -l | grep email_digest
```

There is no test suite, linter, or build step. The venv Python (`.venv/bin/python3`) must be used — system `python3` will fail with `ModuleNotFoundError`.

## Architecture

A Flask app that produces a ranked weekend events list. Regions, cities, persona, and optional sources are all configurable per user from a `/config` page (state lives in `data/config.json`, seeded with Bay Area defaults). Three pieces matter:

**1. Scraping → ranking pipeline** (`agent/search.py` → `agent/claude_agent.py`)
- `search.py` scrapes Eventbrite in parallel via `ThreadPoolExecutor` (cities + state codes pulled from `agent/config.get_scrape_targets()`) plus the Funcheap RSS feed (gated by `config.is_funcheap_enabled()`), dedupes by URL, returns raw events.
- `claude_agent.py` prefilters to ~40 events using keyword scoring (`free`, `family`, `kids`, etc.) and a 3-week date window, then shells out to the **`claude` CLI** via `subprocess.run(["claude", "-p", prompt], ...)`. There is no Anthropic API key — the project depends on the user being logged into Claude Code locally.
- Claude returns JSON (events + day-trip routes); `_extract_json` strips any markdown fences Claude wraps it in.

**2. Two-layer cache** — both in-process dicts, lost on restart:
- `search.py` `_cache` — 2hr TTL on raw scrape results.
- `claude_agent.py` `_output_cache` — 1hr TTL on Claude's JSON output.
- To force a fresh fetch, restart the Flask server.

**3. Two consumers of the same agent**:
- `app.py` — Flask server, exposes `POST /api/events` which calls `get_events_json()` and returns JSON to the vanilla-JS frontend in `templates/index.html`.
- `email_digest.py` — cron entry point. Calls `run_agent()` (a thin wrapper around `get_events_json()` that formats the JSON as markdown), converts to HTML with inline styles for Gmail, and sends via Gmail SMTP using `GMAIL_USER` / `GMAIL_APP_PASSWORD` / `RECIPIENT_EMAIL` from `.env`.

## Things to know before editing

- `build_system_prompt()` in `agent/claude_agent.py` assembles the prompt from `_PROMPT_TEMPLATE` plus the live geography (region → city list from config) plus the optional user persona. Changing the output JSON schema requires updating both `run_agent()`'s markdown formatter (for email) and the frontend in `templates/index.html` (for the web UI).
- To add/remove cities: use the `/config` UI (recommended) or edit `data/config.json` directly. The `DEFAULT_CONFIG` in `agent/config.py` seeds the file on first run and lists the canonical schema (regions with `state` + `enabled`, plus a top-level `preferences` block).
- The prompt's `TIMEFRAME` section is intentionally loose (includes events with missing dates/times, defaults to inclusion). Past tightening here produced empty results — prefer ranking adjustments over harder filters.
- Eventbrite scraping reads JSON-LD `<script type="application/ld+json">` blocks; if Eventbrite changes their markup, `_scrape_eventbrite_city` silently returns `[]` per city (swallowed exceptions) and the user sees an empty list.
