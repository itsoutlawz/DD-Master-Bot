# DamaDam Master Bot v1.0.210

Professional scraping bot for DamaDam.pk with Google Sheets automation, timing records, and flexible run modes.

## Key Enhancements

- **TimingLog sheet** captures every profile scrape with Nickname, Timestamp, Source, and Run Number.
- **Auto-repeat** runs detect the repeat interval (default 5 minutes) and keep the browser loop active without touching RunList in online mode.
- **ProfilesData-only updates in online mode** ensure the task sheet stays untouched while the alphabetical targeting remains in RunList-only sheet mode.
- **Consistent formatting** colors only data rows, keeping headers clean and readable.
- **Command-line + environment limits** mean you can cap a manual run without the scheduler, while scheduled runs ignore limits by default.

## Data Model & Sheets

### ProfilesData
All scraped profiles land here; updates happen in place so the newest data is always current. The script deduplicates on NICK NAME before adding or updating a row.

### TimingLog
New rows are appended for every scrape. Columns: `Nickname | Timestamp | Source | Run Number`. Adjusting this sheet only affects historical timing records; changing the column order will break the log importer.

### RunList
Used exclusively in `--mode sheet`. Set a row to Pending to scrape via RunList, then the bot writes back Complete/Failed without touching this sheet when `--mode online` is active.

### Dashboard
Stores metrics such as `Run Number`, `Profiles Processed`, `Last Run`, and `Run Duration`. Changing these key names requires updating the script’s dashboard helpers.

### NickList
Tracks how many times each nick appears online. This sheet is untouched by the scheduler unless you add new logic.

## Installation

### Prerequisites
- Python 3.11+ (tested)
- Chrome / Chromium with a matching webdriver
- Google Sheets API credentials
- Valid DamaDam cookies stored in `DAMADAM_COOKIES_TXT`

### Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and fill in credentials.
3. Run the scraper manually to verify authentication:
   ```bash
   python Scraper.py --mode online --limit 20
   ```

## Configuration

Store secrets in `.env` or CI variables:

| Variable | Purpose | Effect if changed |
| --- | --- | --- |
| `GOOGLE_SHEET_URL` | Target Google Sheet | Points the bot at a different workbook.
| `GOOGLE_CREDENTIALS_JSON` | Raw service account JSON | Changing this requires re-sharing the sheet with the new account.
| `DAMADAM_COOKIES_TXT` | Login cookies | Must stay in Netscape format; invalid cookies stop the bot.
| `MAX_PROFILES_PER_RUN` | Manual cap per run (0 = unlimited) | Setting a number limits how many ProfilesData entries are touched.
| `REPEAT_INTERVAL_MINUTES` | Delay between auto repeats | Lowering it means faster loops; keep GitHub job timeout in sync.
| `AUTO_REPEAT` | Enables auto-repeat loop | False means script exits after one run.
| `RUN_MODE` | `online` or `sheet` default | Online mode ignores RunList writes; sheet mode updates RunList.
| `SHEET_WRITE_DELAY` | Pause after writes | Increase when hitting Sheets rate limits.

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
  The job reads `AUTO_REPEAT` and `REPEAT_INTERVAL_MINUTES` from the environment. It sleeps for the configured interval after every loop and repeats until the process ends (GitHub caps runs at 8 hours). Changing `REPEAT_INTERVAL_MINUTES` requires adjusting the workflow timeout.

## Scheduling & Automation

The included GitHub workflow runs every 8 hours, cancels any in-flight job, and respects an 8-hour timeout. Scheduled runs force `AUTO_REPEAT=true` and `REPEAT_INTERVAL_MINUTES=5`, so the browser loop keeps re-fetching online profiles every 5 minutes until the job hits the timeout. Manual workflow dispatch allows `run_mode`, `max_profiles`, and the `auto_repeat` toggle.

## Troubleshooting

- **Login failures**: Regenerate `DAMADAM_COOKIES_TXT` and ensure the domain matches `damadam.pk`.
- **Sheets errors**: Confirm the service account email has edit access to the target sheet.
- **RunList data**: RunList rows are only updated in `sheet` mode; online mode writes to ProfilesData and TimingLog only.

## Logging

- Terminal logs include `[HH:MM:SS]` timestamps.
- TimingLog keeps per-profile records for auditing.
- Dashboard metrics show run duration and processed counts.

## License

MIT License — see `LICENSE`.
