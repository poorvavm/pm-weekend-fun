# Setup Guide

Step-by-step instructions to get the Bay Area Weekend Events agent running on your machine.

---

## Prerequisites

- **macOS** (tested on macOS 13+)
- **Python 3.10+** — check with `python3 --version`
- **Claude Code CLI** installed and logged in — check with `claude --version`
- A **Gmail account** (for the weekly email digest)

---

## Step 1 — Clone the project

```bash
git clone <repo-url> pm-weekend-fun
cd pm-weekend-fun
```

---

## Step 2 — Create a virtual environment

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

---

## Step 3 — Configure email

The weekly digest is sent via Gmail. You need a **Gmail App Password** — this is different from your regular Gmail password and takes about 2 minutes to generate.

### 3a. Enable 2-Step Verification (required)

1. Go to → **myaccount.google.com/security**
2. Under "How you sign in to Google", click **2-Step Verification** and turn it on if it's off

### 3b. Generate an App Password

1. Go to → **myaccount.google.com/apppasswords**
2. In the text field, type a name like `weekend-events` and click **Create**
3. Google shows a **16-character code** — copy it (it looks like `abcd efgh ijkl mnop`)

### 3c. Create your `.env` file

```bash
cp .env.example .env
```

Open `.env` and fill in your details:

```
GMAIL_USER=your-gmail@gmail.com
GMAIL_APP_PASSWORD=abcd efgh ijkl mnop
RECIPIENT_EMAIL=recipient@gmail.com
```

| Field | Description |
|---|---|
| `GMAIL_USER` | The Gmail account that sends the email |
| `GMAIL_APP_PASSWORD` | The 16-character code from Step 3b |
| `RECIPIENT_EMAIL` | Who receives the weekly digest (can be the same address) |

---

## Step 4 — Run the web app

```bash
.venv/bin/python3 app.py
```

Open **http://localhost:5050** in your browser and click **Find Events**.

> First load takes ~30 seconds (Claude is processing events). Subsequent clicks are instant thanks to caching.

---

## Step 5 — Test the email

```bash
.venv/bin/python3 email_digest.py
```

Check your inbox — you should receive a styled HTML email with the events table and trip routes.

---

## Step 6 — Set up the weekly cron job

This sends the digest automatically every Thursday at 8am.

```bash
PYTHON="$(pwd)/.venv/bin/python3"
SCRIPT="$(pwd)/email_digest.py"
LOG="/tmp/weekend-events-digest.log"
ENTRY="0 8 * * 4 cd $(pwd) && $PYTHON $SCRIPT >> $LOG 2>&1"
(crontab -l 2>/dev/null | grep -v "email_digest.py"; echo "$ENTRY") | crontab -
```

Verify it's installed:
```bash
crontab -l | grep email_digest
```

To change the time or day, edit with `crontab -e`. The format is:
```
minute hour day month weekday
0      8    *   *     4        ← 8:00am every Thursday
```

Check the log if something goes wrong:
```bash
cat /tmp/weekend-events-digest.log
```

---

## Customising target cities

Edit the `EVENTBRITE_CITY_SLUGS` list in `agent/search.py` to add or remove cities. Use lowercase, hyphenated city names as they appear in Eventbrite URLs (e.g. `san-jose`, `mountain-view`).

## Changing the email schedule

Edit the cron entry with `crontab -e`. To send on Wednesdays at 7am instead:
```
0 7 * * 3 cd /path/to/pm-weekend-fun && .venv/bin/python3 email_digest.py >> /tmp/weekend-events-digest.log 2>&1
```

## Cache behaviour

| Cache | Duration | What it stores |
|---|---|---|
| Event scraping | 2 hours | Raw Eventbrite + Funcheap results |
| Claude output | 1 hour | Ranked JSON of events + routes |

To force a fresh fetch, restart the Flask server (`Ctrl+C` then `python3 app.py`).

---

## Troubleshooting

**`claude: command not found`**
Install Claude Code from claude.ai/code and log in.

**`SMTPAuthenticationError`**
Your App Password is wrong. Re-generate one at myaccount.google.com/apppasswords. Make sure 2-Step Verification is enabled.

**`ModuleNotFoundError`**
Make sure you're using the venv Python: `.venv/bin/python3` not `python3`.

**No events showing**
The event cache is stale or Eventbrite blocked the request. Restart the server to clear the cache.
