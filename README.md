# Weekend Events and Routes Planner

A local web app that finds family-friendly, free & budget-friendly weekend events — powered by Claude AI. Regions are configurable per user (defaults seed Bay Area for convenience). Sends a weekly email digest every Thursday.

## Features

- Scrapes **Eventbrite** (23 target cities) and **Funcheap** for upcoming events
- Claude AI ranks and filters by: free → family-friendly → city-sponsored → outdoor → popular
- Shows **top 10 events** instantly, with a **Show More** button for the rest
- **Filter chips**: All / Free / Family Friendly / East Bay / South Bay / Peninsula / Tri-Valley
- **Day-trip route suggestions** combining nearby events in a single day
- **Weekly email digest** sent automatically every Thursday at 8am
- Results cached for 1 hour — repeat clicks are instant

## Target Cities

East Bay · Tri-Valley · South Bay · Peninsula · Coastal (Half Moon Bay, Santa Cruz, Monterey)

## Stack

| Layer | Tech |
|---|---|
| Backend | Python + Flask |
| AI | Claude CLI (no API key needed — uses your Claude Code session) |
| Scraping | Requests + BeautifulSoup (Eventbrite JSON-LD + Funcheap RSS) |
| Frontend | Vanilla JS + CSS |
| Email | Python smtplib + Gmail SMTP |
| Schedule | macOS crontab |

## Setup

See **[GETTING_STARTED.md](GETTING_STARTED.md)** for full step-by-step instructions including:
- Python + Claude Code CLI prerequisites
- Creating the virtual environment
- Generating a Gmail App Password and configuring `.env`
- Testing the email manually
- Installing the Thursday cron job
- Troubleshooting common errors

Quick start:
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # then fill in your Gmail credentials
.venv/bin/python3 app.py
```

## Run

```bash
# Start the web app
.venv/bin/python3 app.py
# Open http://localhost:5050
```

```bash
# Send the email digest manually
.venv/bin/python3 email_digest.py
```

## Weekly Email

A cron job runs `email_digest.py` every Thursday at 8am automatically.

To check it's installed:
```bash
crontab -l | grep email_digest
```

To change the schedule, edit with `crontab -e`.

## Project Structure

```
vm-weekend-events/
├── app.py                  # Flask server (port 5050)
├── email_digest.py         # Weekly email sender
├── agent/
│   ├── search.py           # Eventbrite + Funcheap scraper (parallel, 2hr cache)
│   └── claude_agent.py     # Claude prompt + JSON parsing (1hr output cache)
├── templates/
│   └── index.html          # Web UI — filter chips, pagination, route cards
├── static/
│   └── style.css
├── .env                    # Gmail credentials (gitignored)
├── .env.example
└── requirements.txt
```

## Event Rules

- **Weekdays** Mon–Thu: 4pm–11pm only
- **Friday**: 2pm–11pm only
- **Saturday & Sunday**: anytime
- Prioritises free, family-friendly, and city-sponsored events
- Covers events up to 3 weeks ahead
