#!/usr/bin/env python3
"""
DamaDam Master Bot - v1.0.210
- Refined auto-repeat, new TimingLog handling, and improved run modes
- ProfilesData only in online mode, controlled limits, clean formatting, scheduler ready
"""

import os
import sys
import re
import time
import json
import random
import argparse
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import *

import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound, APIError

# ============================================================================
# LOAD ENV
# ============================================================================

load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

HOME_URL = "https://damadam.pk/"
ONLINE_URL = "https://damadam.pk/online_kon/"

SHEET_URL = os.getenv('GOOGLE_SHEET_URL', '')
GOOGLE_CREDENTIALS_RAW = os.getenv('GOOGLE_CREDENTIALS_JSON', '')
COOKIES_TXT = os.getenv('DAMADAM_COOKIES_TXT', '')  # ← YE GITHUB SECRET HAI
DAMADAM_USERNAME = os.getenv('DAMADAM_USERNAME', '')
DAMADAM_PASSWORD = os.getenv('DAMADAM_PASSWORD', '')

PAGE_LOAD_TIMEOUT = 30
SHEET_WRITE_DELAY = float(os.getenv('SHEET_WRITE_DELAY', '1.0'))
DEFAULT_MAX_PROFILES = int(os.getenv('MAX_PROFILES_PER_RUN', '0') or '0')
DEFAULT_REPEAT_INTERVAL = int(os.getenv('REPEAT_INTERVAL_MINUTES', '5') or '5')

def parse_bool_env(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')

def parse_int_env(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class RunConfig:
    VALID_MODES = {"online", "sheet"}

    def __init__(self, run_mode: str, max_profiles: int, auto_repeat: bool, repeat_interval: int):
        self.run_mode = run_mode if run_mode in self.VALID_MODES else "online"
        self.max_profiles = max(0, max_profiles)
        self.auto_repeat = auto_repeat
        self.repeat_interval = max(1, repeat_interval)

    @classmethod
    def from_args(cls, args):
        run_mode = (args.mode or os.getenv('RUN_MODE', 'online')).lower()
        auto_repeat = args.auto_repeat or parse_bool_env(os.getenv('AUTO_REPEAT', 'false'))
        repeat_interval = args.repeat_interval if args.repeat_interval is not None else parse_int_env(
            os.getenv('REPEAT_INTERVAL_MINUTES', DEFAULT_REPEAT_INTERVAL), DEFAULT_REPEAT_INTERVAL)

        if args.limit is not None:
            limit = args.limit
        else:
            limit = parse_int_env(os.getenv('MAX_PROFILES_PER_RUN', DEFAULT_MAX_PROFILES), DEFAULT_MAX_PROFILES)

        return cls(run_mode, limit, auto_repeat, repeat_interval)

# Sheets
PROFILES_SHEET_NAME = "ProfilesData"
RUNLIST_SHEET_NAME = "RunList"
DASHBOARD_SHEET_NAME = "Dashboard"
NICK_LIST_SHEET = "NickList"
TIMING_LOG_SHEET_NAME = "TimingLog"
RUNLIST_HEADERS = ["Nickname", "Status", "Remarks", "Source"]

COLUMN_ORDER = [
    "IMAGE", "NICK NAME", "TAGS", "LAST POST", "LAST POST TIME", "FRIEND", "CITY",
    "GENDER", "MARRIED", "AGE", "JOINED", "FOLLOWERS", "STATUS",
    "POSTS", "PROFILE LINK", "INTRO", "SOURCE", "DATETIME SCRAP"
]
COLUMN_TO_INDEX = {name: idx for idx, name in enumerate(COLUMN_ORDER)}
LINK_COLUMNS = {"IMAGE", "LAST POST", "PROFILE LINK"}

TIMING_LOG_HEADERS = ["Nickname", "Timestamp", "Source", "Run Number"]
HEADER_COLOR = {"red": 0.18, "green": 0.35, "blue": 0.72}
HEADER_TEXT_COLOR = {"red": 1.0, "green": 1.0, "blue": 1.0}
ROW_ODD_COLOR = {"red": 1.0, "green": 1.0, "blue": 1.0}
ROW_EVEN_COLOR = {"red": 0.94, "green": 0.97, "blue": 1.0}

# ============================================================================
# HELPER
# ============================================================================

def get_pkt_time():
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=5)

def log_msg(msg):
    print(f"[{get_pkt_time().strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()

# ============================================================================
# BROWSER SETUP
# ============================================================================

def setup_browser():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    driver = webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => false});")
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    return driver

# ============================================================================
# COOKIES LOGIN - 100% CLOUDFLARE BYPASS
# ============================================================================

def _parse_cookies_from_json(cookies_json_str):
    """Parse cookies from JSON format (browser DevTools export)"""
    try:
        cookies_list = json.loads(cookies_json_str)
        if not isinstance(cookies_list, list):
            return []
        
        cookies = []
        for cookie_obj in cookies_list:
            if isinstance(cookie_obj, dict):
                cookie = {
                    'name': cookie_obj.get('name', ''),
                    'value': cookie_obj.get('value', ''),
                    'domain': cookie_obj.get('domain', ''),
                    'path': cookie_obj.get('path', '/'),
                    'secure': cookie_obj.get('secure', False),
                    'httpOnly': cookie_obj.get('httpOnly', False),
                }
                if cookie_obj.get('expires') and cookie_obj['expires'] > 0:
                    cookie['expiry'] = int(cookie_obj['expires'])
                cookies.append(cookie)
        return cookies
    except (json.JSONDecodeError, TypeError):
        return []

def _parse_cookies_from_netscape(cookies_txt_str):
    """Parse cookies from Netscape format (tab-separated)"""
    cookies = []
    for line in cookies_txt_str.strip().split('\n'):
        if line.strip() and not line.startswith('#'):
            parts = line.split('\t')
            if len(parts) >= 7:
                cookie = {
                    'name': parts[5],
                    'value': parts[6],
                    'domain': parts[0],
                    'path': parts[2],
                    'secure': parts[3].lower() == 'true',
                    'httpOnly': parts[4].lower() == 'true' if len(parts) > 4 else False,
                }
                if len(parts) > 4 and parts[4].isdigit():
                    cookie['expiry'] = int(parts[4])
                cookies.append(cookie)
    return cookies

def login_with_cookies(driver):
    log_msg("Applying cookies for login...")
    driver.get(HOME_URL)
    time.sleep(5)

    if not COOKIES_TXT.strip():
        log_msg("DAMADAM_COOKIES_TXT secret missing or empty!")
        return False

    try:
        # Try parsing as JSON first (browser DevTools format)
        cookies = _parse_cookies_from_json(COOKIES_TXT)
        
        # If JSON parsing failed, try Netscape format
        if not cookies:
            cookies = _parse_cookies_from_netscape(COOKIES_TXT)
        
        if not cookies:
            log_msg("No valid cookies found in provided format")
            return False
        
        # Add all cookies to driver
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
            except Exception as e:
                log_msg(f"Failed to add cookie {cookie.get('name')}: {e}")

        driver.refresh()
        time.sleep(6)

        if _detect_logged_in(driver):
            log_msg("Login successful via cookies!")
            return True
        log_msg("Cookies expired or invalid")
        return False
    except Exception as e:
        log_msg(f"Cookie error: {e}")
        return False

def _detect_logged_in(driver):
    return bool(driver.find_elements(By.CSS_SELECTOR, "a[href*='/users/']"))

def login_with_credentials(driver):
    if not DAMADAM_USERNAME or not DAMADAM_PASSWORD:
        log_msg("Missing username/password for manual login")
        return False

    try:
        log_msg("Attempting credentials login...")
        driver.get(Home_LOGIN := f"{HOME_URL}login")
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.NAME, "username")))

        username_field = driver.find_element(By.NAME, "username")
        password_field = driver.find_element(By.NAME, "password")

        username_field.clear()
        username_field.send_keys(DAMADAM_USERNAME)
        time.sleep(0.5)
        password_field.clear()
        password_field.send_keys(DAMADAM_PASSWORD)
        password_field.send_keys(Keys.RETURN)

        time.sleep(4)

        if _detect_logged_in(driver):
            log_msg("Fresh login successful!")
            return True

        log_msg("Manual credential login failed")
        return False
    except Exception as exc:
        log_msg(f"Credential login error: {exc}")
        return False

def login(driver):
    if login_with_cookies(driver):
        return True
    return login_with_credentials(driver)

# ============================================================================
# GOOGLE SHEETS
# ============================================================================

def gsheets_client():
    creds_dict = json.loads(GOOGLE_CREDENTIALS_RAW)
    creds = Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return gspread.authorize(creds)

class Sheets:
    def __init__(self, client):
        self.wb = client.open_by_url(SHEET_URL)
        self.profiles = self._get_or_create(PROFILES_SHEET_NAME, COLUMN_ORDER)
        self.timinglog = self._get_or_create(TIMING_LOG_SHEET_NAME, TIMING_LOG_HEADERS)
        self.runlist = self._get_or_create(RUNLIST_SHEET_NAME, RUNLIST_HEADERS)
        self.dashboard = self._get_or_create(DASHBOARD_SHEET_NAME, ["Metric", "Value"])
        self.nicklist = self._get_or_create(NICK_LIST_SHEET, ["Nick Name", "Times Seen", "First Seen", "Last Seen"])

    def _get_or_create(self, name, headers):
        try:
            ws = self.wb.worksheet(name)
        except WorksheetNotFound:
            ws = self.wb.add_worksheet(name, 10000, len(headers))
            ws.append_row(headers)
            time.sleep(SHEET_WRITE_DELAY)
            self._format_header(ws, len(headers))
        return ws

    def _format_header(self, ws, columns):
        if columns <= 0:
            return
        last_col = self._column_letter(columns - 1)
        ws.format(f"A1:{last_col}1", {
            "backgroundColor": HEADER_COLOR,
            "textFormat": {"bold": True, "foregroundColor": HEADER_TEXT_COLOR},
            "horizontalAlignment": "CENTER"
        })

    def _column_letter(self, index):
        letters = ""
        while index >= 0:
            letters = chr(ord("A") + (index % 26)) + letters
            index = index // 26 - 1
        return letters

    def _format_data_row(self, ws, row_index):
        if row_index <= 1:
            return
        headers = ws.row_values(1)
        if not headers:
            return
        last_col = self._column_letter(len(headers) - 1)
        color = ROW_EVEN_COLOR if row_index % 2 == 0 else ROW_ODD_COLOR
        ws.format(f"A{row_index}:{last_col}{row_index}", {
            "backgroundColor": color,
            "horizontalAlignment": "LEFT"
        })

    def write_profile(self, profile):
        ws = self.profiles
        key = profile.get("NICK NAME", "").lower()
        data = ws.get_all_values()
        headers = data[0] if data else []
        nick_col = headers.index("NICK NAME") + 1 if "NICK NAME" in headers else 1

        row_num = None
        for i, row in enumerate(data[1:], 2):
            if len(row) >= nick_col and row[nick_col - 1].lower() == key:
                row_num = i
                break

        row_values = [profile.get(col, "") for col in COLUMN_ORDER]
        last_col = self._column_letter(len(COLUMN_ORDER) - 1)
        if row_num:
            ws.update(f"A{row_num}:{last_col}{row_num}", [row_values])
        else:
            ws.append_row(row_values)
            row_num = len(data) + 1
        time.sleep(SHEET_WRITE_DELAY)
        self._format_data_row(ws, row_num)

    def log_scrape(self, nickname, timestamp, source, run_number):
        ws = self.timinglog
        row_values = [nickname, timestamp, source, run_number]
        inserted_row = len(ws.get_all_values()) + 1
        ws.append_row(row_values)
        time.sleep(SHEET_WRITE_DELAY)
        self._format_data_row(ws, inserted_row)

    def get_pending_runlist(self, limit=0):
        data = self.runlist.get_all_values()
        if len(data) <= 1:
            return []

        headers = data[0]
        def _index(name, default):
            try:
                return headers.index(name)
            except ValueError:
                return default

        nick_idx = _index("Nickname", 0)
        status_idx = _index("Status", 1)
        source_idx = _index("Source", 3)
        entries = []
        for row_idx, row in enumerate(data[1:], start=2):
            status = row[status_idx].strip().lower() if len(row) > status_idx else ""
            if status in ("complete", "done"):
                continue
            nickname = row[nick_idx].strip() if len(row) > nick_idx else ""
            source = (row[source_idx].strip() if len(row) > source_idx else "").strip() or "Sheet"
            entries.append({"row": row_idx, "nickname": nickname, "source": source})
            if limit and len(entries) >= limit:
                break
        return entries

    def update_runlist_entry(self, row_index, nickname, status, remarks, source):
        values = [nickname, status, remarks, source]
        last_col = self._column_letter(len(RUNLIST_HEADERS) - 1)
        self.runlist.update(f"A{row_index}:{last_col}{row_index}", [values])
        time.sleep(SHEET_WRITE_DELAY)
        self._format_data_row(self.runlist, row_index)

    def get_dashboard_metric(self, key):
        data = self.dashboard.get_all_values()
        for row in data:
            if row and row[0] == key:
                return row[1] if len(row) > 1 else ""
        return ""

    def update_dashboard(self, metrics):
        ws = self.dashboard
        data = ws.get_all_values()
        existing = {row[0]: i + 1 for i, row in enumerate(data) if row}
        for key, val in metrics.items():
            if key in existing:
                ws.update_cell(existing[key], 2, val)
            else:
                ws.append_row([key, val])

# ============================================================================
# SCRAPING
# ============================================================================

def fetch_online_nicknames(driver):
    log_msg("Fetching online users...")
    driver.get(ONLINE_URL)
    time.sleep(5)
    names = []
    try:
        items = driver.find_elements(By.CSS_SELECTOR, "li.mbl.cl.sp b")
        for b in items:
            nick = b.text.strip()
            if nick and len(nick) >= 3 and any(c.isalpha() for c in nick):
                names.append(nick)
    except Exception:
        pass
    log_msg(f"Found {len(names)} online users")
    return names

def scrape_profile(driver, nickname):
    url = f"https://damadam.pk/users/{nickname}/"
    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
        now = get_pkt_time()
        data = {
            "IMAGE": "",
            "NICK NAME": nickname,
            "TAGS": "",
            "LAST POST": "",
            "LAST POST TIME": "",
            "FRIEND": "",
            "CITY": "",
            "GENDER": "",
            "MARRIED": "",
            "AGE": "",
            "JOINED": "",
            "FOLLOWERS": "",
            "STATUS": "",
            "POSTS": "",
            "PROFILE LINK": url.rstrip('/'),
            "INTRO": "",
            "SOURCE": "Online",
            "DATETIME SCRAP": now.strftime("%d-%b-%y %I:%M %p")
        }
        return data
    except Exception as exc:
        log_msg(f"Failed to scrape {nickname}: {exc}")
        return None

# ============================================================================
# RUN HELPERS
# ============================================================================

def compute_next_run_number(sheets):
    raw_value = sheets.get_dashboard_metric("Run Number")
    try:
        return int(raw_value) + 1
    except (TypeError, ValueError):
        return 1

def run_online_mode(sheets, driver, run_number, limit):
    online_nicks = fetch_online_nicknames(driver)
    if not online_nicks:
        log_msg("No online nicknames found.")
        return 0, 0

    processed = 0
    for idx, nick in enumerate(online_nicks, start=1):
        if limit > 0 and processed >= limit:
            break
        profile = scrape_profile(driver, nick)
        if profile:
            sheets.write_profile(profile)
            sheets.log_scrape(nick, profile["DATETIME SCRAP"], "Online", run_number)
            processed += 1
            log_msg(f"[{idx}/{len(online_nicks)}] Saved profile: {nick}")
        else:
            log_msg(f"[{idx}/{len(online_nicks)}] Failed to scrape: {nick}")
        time.sleep(random.uniform(1, 2))

    return processed, len(online_nicks)

def run_sheet_mode(sheets, driver, run_number, limit):
    entries = sheets.get_pending_runlist(limit)
    if not entries:
        log_msg("No pending RunList entries to process.")
        return 0, 0

    processed = 0
    total = len(entries)
    for idx, entry in enumerate(entries, start=1):
        nickname = entry.get("nickname") or ""
        if not nickname:
            log_msg(f"Skipping empty entry at row {entry['row']}")
            continue

        log_msg(f"[{idx}/{total}] Processing RunList entry: {nickname}")
        profile = scrape_profile(driver, nickname)
        status = "Complete" if profile else "Failed"
        remarks = "Profile captured" if profile else "Profile not found"
        if profile:
            sheets.write_profile(profile)
            sheets.log_scrape(nickname, profile["DATETIME SCRAP"], entry["source"], run_number)
            processed += 1

        sheets.update_runlist_entry(entry["row"], nickname, status, remarks, entry["source"])
        time.sleep(random.uniform(1, 2))

    return processed, total

def log_run_summary(run_number, run_mode, processed, total_candidates, duration_seconds):
    log_msg("==========================================")
    log_msg(f"Run #{run_number} | Mode: {run_mode.capitalize()} | Duration: {duration_seconds}s")
    log_msg(f"Profiles processed: {processed}/{total_candidates if total_candidates else 'N/A'}")
    log_msg("==========================================")

# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="DamaDam Master Bot")
    parser.add_argument('--mode', choices=['online', 'sheet'], help='Run mode (online or sheet)', default=None)
    parser.add_argument('--limit', type=int, default=None, help='Maximum profiles to process (0 = unlimited)')
    parser.add_argument('--auto-repeat', action='store_true', help='Keep repeating runs every interval')
    parser.add_argument('--repeat-interval', type=int, default=None, help='Delay between auto-repeat runs (minutes)')
    args = parser.parse_args()

    run_config = RunConfig.from_args(args)

    print("\n" + "=" * 80)
    print("DamaDam Master Bot v1.0.210 - CLOUDFLARE BYPASS ACTIVE")
    print("=" * 80 + "\n")

    driver = setup_browser()
    if not login_with_cookies(driver):
        log_msg("LOGIN FAILED - Update DAMADAM_COOKIES_TXT secret!")
        driver.quit()
        return

    try:
        client = gsheets_client()
        sheets = Sheets(client)
    except Exception as exc:
        log_msg(f"Sheets error: {exc}")
        driver.quit()
        return

    run_number = compute_next_run_number(sheets)
    iteration = 0
    try:
        while True:
            iteration += 1
            log_msg(f"Starting run #{run_number} (iteration {iteration}) in {run_config.run_mode} mode")
            start_time = get_pkt_time()

            if run_config.run_mode == 'sheet':
                processed, total_candidates = run_sheet_mode(sheets, driver, run_number, run_config.max_profiles)
            else:
                processed, total_candidates = run_online_mode(sheets, driver, run_number, run_config.max_profiles)

            completion_time = get_pkt_time()
            duration_seconds = int((completion_time - start_time).total_seconds())
            sheets.update_dashboard({
                "Last Run": completion_time.strftime("%d-%b-%y %I:%M %p"),
                "Profiles Processed": processed,
                "Run Number": run_number,
                "Run Duration": f"{duration_seconds}s"
            })

            log_run_summary(run_number, run_config.run_mode, processed, total_candidates, duration_seconds)

            run_number += 1

            if not run_config.auto_repeat:
                break

            log_msg(f"Waiting {run_config.repeat_interval} minutes before the next run...")
            time.sleep(run_config.repeat_interval * 60)
    finally:
        log_msg("Shutting down browser...")
        driver.quit()

if __name__ == "__main__":
    main()
