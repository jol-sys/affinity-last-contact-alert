"""
Affinity "Last Contact" Milestone Alert
========================================
Checks the "LP Fundraising Opportunities" list in Affinity. For opportunities
with Status "Blurb / Teaser sent", "Pitch / Case Study sent", or "Dataroom",
sends one daily email listing those whose Last Contact date is exactly
10, 20, or 30 days ago (in Europe/Berlin). If no opportunity hits a
milestone today, no email is sent.

Secrets are read from environment variables (set as GitHub Actions secrets).
"""

import json
import os
import smtplib
import ssl
import urllib.request
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from zoneinfo import ZoneInfo

# ── Configuration ──────────────────────────────────────────────────────────────
AFFINITY_API_KEY = os.environ["AFFINITY_API_KEY"]
GMAIL_ADDRESS = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
EMAIL_TO = os.environ["EMAIL_TO"]

LIST_ID = 223179
STATUS_FIELD_ID = "field-4152109"
LAST_CONTACT_FIELD_ID = "last-contact"
TARGET_STATUSES = {"Blurb / Teaser sent", "Pitch / Case Study sent", "Dataroom"}
MILESTONE_DAYS = (15,)

BERLIN_TZ = ZoneInfo("Europe/Berlin")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
V2_BASE = "https://api.affinity.co/v2"


# ── Affinity API ───────────────────────────────────────────────────────────────
def affinity_v2_get(url):
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {AFFINITY_API_KEY}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def get_milestone_opportunities(today_berlin):
    """Return opportunities whose last contact was exactly 10, 20, or 30
    calendar days ago in Berlin time."""
    alerts = []
    url = (
        f"{V2_BASE}/lists/{LIST_ID}/list-entries"
        f"?fieldIds={STATUS_FIELD_ID}&fieldIds={LAST_CONTACT_FIELD_ID}&limit=100"
    )

    while url:
        data = affinity_v2_get(url)
        for entry in data.get("data", []):
            fields = entry.get("entity", {}).get("fields", [])
            status_text = None
            last_contact_date = None

            for f in fields:
                if f["id"] == STATUS_FIELD_ID:
                    val = (f.get("value") or {}).get("data") or {}
                    status_text = val.get("text") if val else None
                elif f["id"] == LAST_CONTACT_FIELD_ID:
                    interaction = (f.get("value") or {}).get("data")
                    if interaction:
                        # emails/chats have sentAt, meetings have startTime
                        raw = interaction.get("sentAt") or interaction.get("startTime")
                        if raw:
                            last_contact_date = datetime.fromisoformat(
                                raw.replace("Z", "+00:00")
                            )

            if status_text not in TARGET_STATUSES or last_contact_date is None:
                continue

            last_berlin_date = last_contact_date.astimezone(BERLIN_TZ).date()
            days_since = (today_berlin - last_berlin_date).days

            if days_since in MILESTONE_DAYS:
                alerts.append({
                    "name": entry["entity"]["name"],
                    "status": status_text,
                    "last_contact": last_berlin_date.isoformat(),
                    "days_since": days_since,
                })

        url = data.get("pagination", {}).get("nextUrl")

    return alerts


# ── Email ──────────────────────────────────────────────────────────────────────
def build_email_body(alerts):
    rows = ""
    for a in sorted(alerts, key=lambda x: (-x["days_since"], x["name"])):
        color = "#cc4400"
        rows += (
            f"<tr>"
            f"<td style='padding:6px 12px;border:1px solid #ddd'>{a['name']}</td>"
            f"<td style='padding:6px 12px;border:1px solid #ddd'>{a['status']}</td>"
            f"<td style='padding:6px 12px;border:1px solid #ddd'>{a['last_contact']}</td>"
            f"<td style='padding:6px 12px;border:1px solid #ddd;font-weight:bold;"
            f"color:{color}'>"
            f"{a['days_since']} days</td>"
            f"</tr>"
        )

    return f"""\
<html><body>
<p>The following <strong>{len(alerts)}</strong> opportunities reached
<strong>15 days without contact</strong> today:</p>
<table style='border-collapse:collapse;font-family:Arial,sans-serif;font-size:14px'>
<tr style='background:#f4f4f4'>
  <th style='padding:8px 12px;border:1px solid #ddd;text-align:left'>Opportunity</th>
  <th style='padding:8px 12px;border:1px solid #ddd;text-align:left'>Status</th>
  <th style='padding:8px 12px;border:1px solid #ddd;text-align:left'>Last Contact</th>
  <th style='padding:8px 12px;border:1px solid #ddd;text-align:left'>Days Since</th>
</tr>
{rows}
</table>
<p style='color:#888;font-size:12px;margin-top:20px'>
This is an automated alert from the Affinity Last Contact checker.</p>
</body></html>"""


def send_email(subject, html_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = EMAIL_TO
    msg.attach(MIMEText(html_body, "html"))

    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls(context=context)
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, EMAIL_TO, msg.as_string())


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    today_berlin = datetime.now(BERLIN_TZ).date()
    print(f"[{datetime.now(timezone.utc).isoformat()}] "
          f"Checking milestones for {today_berlin}...")

    alerts = get_milestone_opportunities(today_berlin)
    print(f"  {len(alerts)} opportunities hit a milestone today.")

    if alerts:
        subject = f"⚠ {len(alerts)} LP opportunit{'y' if len(alerts) == 1 else 'ies'} at 15 days without contact"
        send_email(subject, build_email_body(alerts))
        print(f"  Email sent to {EMAIL_TO}.")
    else:
        print("  No opportunities at the 15-day mark today. No email sent.")


if __name__ == "__main__":
    main()
