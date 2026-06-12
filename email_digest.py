"""
Weekly events digest — runs every Thursday via cron.
Fetches events, asks Claude to summarize, sends a styled HTML email.
"""

import os
import smtplib
import sys
from datetime import date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import markdown as md
from dotenv import load_dotenv

from agent.claude_agent import run_agent

load_dotenv()

GMAIL_USER       = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT_EMAIL  = os.environ["RECIPIENT_EMAIL"]


def _weekend_label():
    today = date.today()
    days_until_sat = (5 - today.weekday()) % 7 or 7
    sat = today + timedelta(days=days_until_sat)
    sun = sat + timedelta(days=1)
    return f"{sat.strftime('%b %d')} – {sun.strftime('%b %d, %Y')}"


def _to_html(markdown_text):
    body_html = md.markdown(markdown_text, extensions=["tables"])

    # Inline styles so Gmail renders them correctly
    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
             background:#f1f5f9;margin:0;padding:24px;">

  <div style="max-width:720px;margin:0 auto;">

    <!-- Header -->
    <div style="background:linear-gradient(135deg,#0f172a,#1d4ed8);
                border-radius:14px 14px 0 0;padding:28px 32px;color:#fff;">
      <h1 style="margin:0;font-size:1.5rem;font-weight:800;">
        Weekend Events and Routes Planner
      </h1>
      <p style="margin:6px 0 0;color:#93c5fd;font-size:0.9rem;">
        {_weekend_label()} &nbsp;·&nbsp; Family-friendly &nbsp;·&nbsp; Free &amp; budget friendly
      </p>
    </div>

    <!-- Content -->
    <div style="background:#fff;border-radius:0 0 14px 14px;
                padding:28px 32px;box-shadow:0 4px 20px rgba(0,0,0,0.06);">

      <style>
        table {{border-collapse:collapse;width:100%;font-size:0.85rem;margin-bottom:1.5rem;}}
        th {{background:#0f172a;color:#e2e8f0;padding:10px 12px;text-align:left;font-size:0.75rem;text-transform:uppercase;letter-spacing:0.5px;}}
        td {{padding:9px 12px;border-bottom:1px solid #e2e8f0;vertical-align:top;}}
        tr:nth-child(even) td {{background:#f8fafc;}}
        a {{color:#4f46e5;text-decoration:none;}}
        h2 {{color:#0f172a;border-bottom:2px solid #4f46e5;padding-bottom:6px;
             margin:24px 0 14px;font-size:1.05rem;}}
        strong {{color:#0f172a;}}
        p {{line-height:1.65;color:#334155;}}
        ul {{padding-left:20px;}} li {{margin:4px 0;line-height:1.5;color:#334155;}}
        blockquote {{border-left:3px solid #c7d2fe;padding:8px 14px;
                     background:#f5f3ff;border-radius:0 8px 8px 0;
                     color:#64748b;font-size:0.85rem;margin:12px 0;}}
      </style>

      {body_html}

    </div>

    <!-- Footer -->
    <p style="text-align:center;color:#94a3b8;font-size:0.78rem;margin-top:16px;">
      Sent every Thursday · Weekend Events and Routes Planner
    </p>
  </div>

</body>
</html>
"""


def send_email(subject, html):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = RECIPIENT_EMAIL
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, RECIPIENT_EMAIL, msg.as_string())


def main():
    print("Fetching events and asking Claude…")
    result = run_agent()

    weekend = _weekend_label()
    subject = f"Weekend Events: {weekend}"
    html = _to_html(result)

    print(f"Sending to {RECIPIENT_EMAIL}…")
    send_email(subject, html)
    print("Done.")


if __name__ == "__main__":
    main()
