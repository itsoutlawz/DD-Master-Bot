# DamaDam Master Bot v1.0.210

Professional scraping bot for DamaDam.pk with Google Sheets automation, timing records, and flexible run modes.

## Key Enhancements

- **TimingLog sheet** captures every profile scrape with Nickname, Timestamp, Source, and Run Number.
- **Auto-repeat** runs detect the repeat interval (default 5 minutes) and keep the browser loop active without touching RunList in online mode.
- **ProfilesData-only updates in online mode** ensure the task sheet stays untouched while the RunList workflow continues to drive manual tasks.
- **Consistent formatting** colors only data rows so headers remain readable and uniform across sheets.
- **Command-line + environment limits** let manual runs cap processed profiles without changing scheduled behavior.

## Data Model & Sheets

### ProfilesData

All scraped profiles land here; updates happen in place so the newest data is always current. The bot deduplicates on `NICK NAME` before writing a row.

### TimingLog

New rows capture every scrape. Columns: `Nickname | Timestamp | Source | Run Number`. This sheet exists solely for timing audit trails, so changing the order of those columns will break the logging helpers.

### RunList

Used only when `--mode sheet` (or RUN_MODE=sheet). The bot marks rows Complete/Failed, but online mode never updates this sheet and only writes to ProfilesData + TimingLog.

### Dashboard

Stores metrics such as `Run Number`, `Profiles Processed`, `Last Run`, and `Run Duration`. Renaming these keys requires updating the bot’s dashboard helpers.

### NickList

Tracks how often each nick appears online. This sheet remains untouched unless additional logic is added.

## Installation

### Prerequisites

- Python 3.11+ (tested)
- Chrome / Chromium with a matching webdriver
- Google Sheets API credentials
- Valid DamaDam cookies stored in `DAMADAM_COOKIES_TXT`

### Setup

1. Install dependencies.

   ```bash
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and fill in the secrets.

3. Run the scraper manually for verification.

   ```bash
   python Scraper.py --mode online --limit 20
   ```

## Configuration

Store secrets in `.env` or in the environment:

| Variable | Purpose | Effect if changed |
| --- | --- | --- |
| `GOOGLE_SHEET_URL` | Target Google Sheet | Points the bot at a different workbook. |
| `GOOGLE_CREDENTIALS_JSON` | Raw service account JSON | Changing this requires re-sharing the sheet with the new account. |
| `DAMADAM_COOKIES_TXT` | Login cookies | Must stay in Netscape format; invalid cookies stop the bot. |
| `MAX_PROFILES_PER_RUN` | Manual cap per run (0 = unlimited) | Setting a number limits how many ProfilesData entries are touched. |
| `REPEAT_INTERVAL_MINUTES` | Delay between auto repeats | Lowering it means faster loops; keep workflow timeout in sync. |
| `AUTO_REPEAT` | Enables the auto-repeat loop | False means the script exits after one run. |
| `RUN_MODE` | `online` or `sheet` default | Online mode ignores RunList writes; sheet mode updates RunList. |
| `SHEET_WRITE_DELAY` | Pause after writes | Increase when hitting Sheets rate limits. |

## Usage

- **Manual (local or workflow)**

   ```bash
   python Scraper.py --mode online --limit 30
   python Scraper.py --mode sheet --limit 10
   ```

   Manual runs obey `--limit` and `MAX_PROFILES_PER_RUN`. Use `--auto-repeat --repeat-interval 5` to keep looping locally.

- **Auto / Scheduler-friendly**

   ```bash
   python Scraper.py --mode online
   ```

   The job reads `AUTO_REPEAT` and `REPEAT_INTERVAL_MINUTES` from the environment. It sleeps for the configured interval after every loop and repeats until the process ends (GitHub caps runs at 8 hours). Changing the interval requires aligning workflow timeouts.

## Scheduling & Automation

The GitHub workflow runs every 8 hours, cancels any in-flight job, and respects an 8-hour timeout. Scheduled runs force `AUTO_REPEAT=true` and `REPEAT_INTERVAL_MINUTES=5`, so the browser loop keeps refreshing online profiles every 5 minutes until the job hits the timeout. Manual workflow dispatch accepts `run_mode`, `max_profiles`, and the `auto_repeat` toggle.

## Troubleshooting

- **Login failures**: Regenerate `DAMADAM_COOKIES_TXT` and ensure the domain matches `damadam.pk`.
- **Sheets errors**: Confirm the service account email has edit access.
- **RunList data**: RunList rows are only updated in `sheet` mode; online mode writes to ProfilesData and TimingLog only.

## Logging

- Terminal logs include `[HH:MM:SS]` timestamps.
- TimingLog keeps per-profile records for auditing.
- Dashboard metrics show run duration and processed counts.

## License

MIT License — see `LICENSE`.
