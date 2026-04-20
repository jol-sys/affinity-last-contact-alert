"""
Affinity "Last Contact" Alert Script
=====================================
Checks the "LP Fundraising Opportunities" list in Affinity for opportunities
where Status is "Blurb / Teaser sent", "Pitch / Case Study sent", or "Dataroom"
AND the "Last Contact" date is 10+ days ago. Sends an email summary.

Secrets are read from environment variables (set as GitHub Actions secrets).
"""

import json
import os
import smtplib
import ssl
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
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
DAYS_THRESHOLD = 10

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
V2_BASE = "https://api.affinity.co/v2"


# ── Affinity API ───────────────────────────────────────────────────────────────
def affinity_v2_get(url):
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {AFFINITY_API_KEY}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def get_overdue_opportunities(threshold):
    alerts = []
    url = (
        f"{V2_BASE}/lists/{LIST_ID}/list-entries"
        f"?fieldIds={STATUS_FIELD_ID}&fieldIds={LAST_CONTACT_FIELD_ID}&limit=100"
    )

    total_matching = 0
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
                        # emails have sentAt, meetings have startTime,
                        # chat messages also have sentAt
                        raw = interaction.get("sentAt") or interaction.get("startTime")
                        if raw:
                            last_contact_date = datetime.fromisoformat(
                                raw.replace("Z", "+00:00")
                            )

            if status_text not in TARGET_STATUSES:
                continue

            total_matching += 1
            name = entry["entity"]["name"]

            if last_contact_date is None:
                alerts.append({
                    "name": name,
                    "status": status_text,
                    "last_contact": "No record",
                    "days_since": 999,
                })
            elif last_contact_date < threshold:
                days_since = (datetime.now(timezone.utc) - last_contact_date).days
                alerts.append({
                    "name": name,
                    "status": status_text,
                    "last_contact": last_contact_date.strftime("%Y-%m-%d"),
                    "days_since": days_since,
                })

        url = data.get("pagination", {}).get("nextUrl")

    return alerts, total_matching


# ── Email ──────────────────────────────────────────────────────────────────────
def build_email_body(alerts):
    rows = ""
    for a in sorted(alerts, key=lambda x: x["days_since"], reverse=True):
        color = "red" if a["days_since"] >= 20 else "orange"
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
<p>The following <strong>{len(alerts)}</strong> opportunities have not been contacted
in <strong>{DAYS_THRESHOLD}+ days</strong> and are in an active status:</p>
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
    # Only run if we're in the 09:xx hour in Berlin (skip the off-DST duplicate run).
    # Bypass this guard by setting ALWAYS_RUN=1 (e.g. for manual workflow_dispatch).
    berlin_now = datetime.now(ZoneInfo("Europe/Berlin"))
    if berlin_now.hour != 9 and os.environ.get("ALWAYS_RUN") != "1":
        print(f"Berlin time is {berlin_now:%H:%M} — not 09:xx, skipping.")
        return

    now = datetime.now(timezone.utc)
    threshold = now - timedelta(days=DAYS_THRESHOLD)

    print(f"[{now.isoformat()}] Fetching opportunities...")
    alerts, total_matching = get_overdue_opportunities(threshold)
    print(f"  {total_matching} opportunities match target statuses.")
    print(f"  {len(alerts)} are overdue ({DAYS_THRESHOLD}+ days without contact).")

    if alerts:
        subject = f"⚠ {len(alerts)} LP opportunities overdue for contact"
        html_body = build_email_body(alerts)
        send_email(subject, html_body)
        print(f"  Email sent to {EMAIL_TO}.")
    else:
        print("  No overdue opportunities. No email sent.")


if __name__ == "__main__":
    main()
