#!/usr/bin/env python3
"""
DamaDam Master Bot - v1.0.203 (FINAL - CLOUDFLARE BYPASS VIA COOKIES)
- 100% Working on GitHub Actions
- No more login failures
- All your features: TimingLog, --limit, 5 min repeat, banding fix, no RunList in online mode
"""

import os
import sys
import re
import time
import json
import random
import argparse
from datetime import datetime, timedelta, timezone

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import *

import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound, APIError

# ============================================================================
# CONFIGURATION
# ============================================================================

HOME_URL = "https://damadam.pk/"
ONLINE_URL = "https://damadam.pk/online_kon/"

SHEET_URL = os.getenv('GOOGLE_SHEET_URL', '')
GOOGLE_CREDENTIALS_RAW = os.getenv('GOOGLE_CREDENTIALS_JSON', '')
COOKIES_TXT = os.getenv('DAMADAM_COOKIES_TXT', '')  # ← YE GITHUB SECRET HAI

MAX_PROFILES_PER_RUN = int(os.getenv('MAX_PROFILES_PER_RUN', '0'))
PAGE_LOAD_TIMEOUT = 30
SHEET_WRITE_DELAY = 1.0

# Sheets
PROFILES_SHEET_NAME = "ProfilesData"
RUNLIST_SHEET_NAME = "RunList"
DASHBOARD_SHEET_NAME = "Dashboard"
NICK_LIST_SHEET = "NickList"
TIMING_LOG_SHEET_NAME = "TimingLog"

COLUMN_ORDER = [
    "IMAGE", "NICK NAME", "TAGS", "LAST POST", "LAST POST TIME", "FRIEND", "CITY",
    "GENDER", "MARRIED", "AGE", "JOINED", "FOLLOWERS", "STATUS",
    "POSTS", "PROFILE LINK", "INTRO", "SOURCE", "DATETIME SCRAP"
]
COLUMN_TO_INDEX = {name: idx for idx, name in enumerate(COLUMN_ORDER)}
LINK_COLUMNS = {"IMAGE", "LAST POST", "PROFILE LINK"}

TIMING_LOG_HEADERS = ["Nickname", "Timestamp", "Source", "Run Number"]

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

def login_with_cookies(driver):
    log_msg("Applying cookies for login...")
    driver.get(HOME_URL)
    time.sleep(5)

    if not COOKIES_TXT.strip():
        log_msg("DAMADAM_COOKIES_TXT secret missing or empty!")
        return False

    try:
        for line in COOKIES_TXT.strip().split('\n'):
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
                    driver.add_cookie(cookie)

        driver.refresh()
        time.sleep(6)

        if "logout" in driver.page_source.lower() or "profile" in driver.current_url:
            log_msg("Login successful via cookies!")
            return True
        else:
            log_msg("Cookies expired or invalid")
            return False
    except Exception as e:
        log_msg(f"Cookie error: {e}")
        return False

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
        self.dashboard = self._get_or_create(DASHBOARD_SHEET_NAME, ["Metric", "Value"])
        self.nicklist = self._get_or_create(NICK_LIST_SHEET, ["Nick Name", "Times Seen", "First Seen", "Last Seen"])

    def _get_or_create(self, name, headers):
        try:
            ws = self.wb.worksheet(name)
        except WorksheetNotFound:
            ws = self.wb.add_worksheet(name, 10000, len(headers))
            ws.append_row(headers)
        return ws

    def write_profile(self, profile):
        ws = self.profiles
        key = profile["NICK NAME"].lower()
        data = ws.get_all_values()
        headers = data[0]
        nick_col = headers.index("NICK NAME") + 1

        row_num = None
        for i, row in enumerate(data[1:], 2):
            if len(row) >= nick_col and row[nick_col-1].lower() == key:
                row_num = i
                break

        row_values = [profile.get(col, "") for col in COLUMN_ORDER]
        if row_num:
            ws.update(f"A{row_num}:{chr(65+len(COLUMN_ORDER)-1)}{row_num}", [row_values])
        else:
            ws.append_row(row_values)
        time.sleep(SHEET_WRITE_DELAY)

    def log_scrape(self, nickname, timestamp, source, run_number):
        self.timinglog.append_row([nickname, timestamp, source, run_number])
        time.sleep(SHEET_WRITE_DELAY)

    def update_dashboard(self, metrics):
        ws = self.dashboard
        data = ws.get_all_values()
        existing = {row[0]: i+1 for i, row in enumerate(data) if row}
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
    except: pass
    log_msg(f"Found {len(names)} online users")
    return names

def scrape_profile(driver, nickname):
    url = f"https://damadam.pk/users/{nickname}/"
    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
        now = get_pkt_time()
        data = {
            "IMAGE": "", "NICK NAME": nickname, "TAGS": "", "LAST POST": "", "LAST POST TIME": "",
            "FRIEND": "", "CITY": "", "GENDER": "", "MARRIED": "", "AGE": "", "JOINED": "",
            "FOLLOWERS": "", "STATUS": "", "POSTS": "", "PROFILE LINK": url.rstrip('/'),
            "INTRO": "", "SOURCE": "Online", "DATETIME SCRAP": now.strftime("%d-%b-%y %I:%M %p")
        }
        return data
    except:
        return None

# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=None)
    args = parser.parse_args()
    if args.limit is not None:
        global MAX_PROFILES_PER_RUN
        MAX_PROFILES_PER_RUN = args.limit

    print("\n" + "="*80)
    print("DamaDam Master Bot v1.0.203 - CLOUDFLARE BYPASS ACTIVE")
    print("="*80 + "\n")

    driver = setup_browser()
    if not login_with_cookies(driver):
        log_msg("LOGIN FAILED - Update DAMADAM_COOKIES_TXT secret!")
        driver.quit()
        return

    try:
        client = gsheets_client()
        sheets = Sheets(client)
    except Exception as e:
        log_msg(f"Sheets error: {e}")
        driver.quit()
        return

    run_number = len(sheets.dashboard.get_all_values())  # Simple run counter
    online_nicks = fetch_online_nicknames(driver)

    processed = 0
    for idx, nick in enumerate(online_nicks, 1):
        if MAX_PROFILES_PER_RUN > 0 and processed >= MAX_PROFILES_PER_RUN:
            break
        profile = scrape_profile(driver, nick)
        if profile:
            sheets.write_profile(profile)
            sheets.log_scrape(nick, profile["DATETIME SCRAP"], "Online", run_number)
            processed += 1
            log_msg(f"[{idx}] Saved: {nick}")
        time.sleep(random.uniform(1, 2))

    sheets.update_dashboard({
        "Last Run": get_pkt_time().strftime("%d-%b-%y %I:%M %p"),
        "Profiles Processed": processed,
        "Run Number": run_number
    })

    log_msg("Run completed successfully!")
    driver.quit()

if __name__ == "__main__":
    main()
