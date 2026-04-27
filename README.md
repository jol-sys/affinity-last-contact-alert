# Affinity Last Contact Milestone Alert

Runs daily at 09:00 Europe/Berlin via GitHub Actions. Checks the
"LP Fundraising Opportunities" list in Affinity. For opportunities in an
active status (`Blurb / Teaser sent`, `Pitch / Case Study sent`, or
`Dataroom`), it emails `EMAIL_TO` whenever an opportunity's Last Contact
is **exactly 10, 20, or 30 days ago**. If no opportunity hits a milestone
on a given day, no email is sent.

## Setup

### 1. Create the repo

1. Sign in to GitHub on a company account.
2. Create a new **private** repository (suggested name: `affinity-last-contact-alert`).
3. Upload the contents of this folder (drag-and-drop on the GitHub web UI works).

### 2. Add secrets

In the repo, go to **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret name          | Value                                          |
|----------------------|------------------------------------------------|
| `AFFINITY_API_KEY`   | `7mDH0cht3Fu4cS5vZCf43JcvHq6C-o8t6xyobANkYiI`  |
| `GMAIL_ADDRESS`      | `affinityreminder@gmail.com`                   |
| `GMAIL_APP_PASSWORD` | `gwbv rrrt rsiq droo`                          |
| `EMAIL_TO`           | `jol@yzr-capital.com`                          |

### 3. Enable Actions

If prompted, click **"I understand my workflows, go ahead and enable them"**.

### 4. Test it manually

**Actions** tab → **Daily Affinity Last Contact Alert** → **Run workflow**.
Set the env var `ALWAYS_RUN=1` (already wired up in the workflow) to
bypass the 09:00 time check.

## How the schedule works

GitHub Actions cron runs in UTC only. To stay at 09:00 Berlin year-round,
the workflow fires twice daily (07:15 UTC and 08:15 UTC) and the Python
script exits early unless the Berlin local hour is 09. This makes the
email arrive once per day regardless of DST.

## Important: don't miss a day

The milestone is checked by exact day count, so if a daily run is skipped
(e.g. GitHub Actions outage), an opportunity that was 10 days out will
become 11 days out the next day and slip past without an alert. You can
always re-run manually via the Actions UI to catch up.

## To change

- **Recipient**: update `EMAIL_TO` secret
- **Milestones**: edit `MILESTONE_DAYS = (10, 20, 30)` in the script
- **Statuses to monitor**: edit `TARGET_STATUSES` in the script
- **Run time**: edit the `cron:` lines in `.github/workflows/daily-alert.yml`
  (UTC) and update the hour check in `main()` accordingly

## Local testing

```bash
export AFFINITY_API_KEY="..."
export GMAIL_ADDRESS="..."
export GMAIL_APP_PASSWORD="..."
export EMAIL_TO="..."
export ALWAYS_RUN=1   # bypass the 09:00 Berlin time gate
python affinity_last_contact_alert.py
```
