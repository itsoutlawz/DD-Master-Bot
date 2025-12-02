#!/usr/bin/env python3
"""
DamaDam Master Bot - v1.0.202 (Updated)
- Scrapes online users and processes them like Target Bot
- Writes all data to "ProfilesData" sheet
- Uses "RunList" for task management only in sheet mode
- Uses "CheckList" for tags/categories
- Professional terminal display with detailed metrics
- Auto-optimizes batch size and delays after 10 profiles
- Duplicate check with Notes instead of highlighting
- Comprehensive API rate limiting and error handling
- New: TimingLog sheet for scrape records
- Fixed: Banding skips header, consistent formatting
- New: Command-line --limit overrides .env
"""

import os
import sys
import re
import time
import json
import random
from datetime import datetime, timedelta, timezone
import argparse

# ------------ Selenium Imports ------------
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# ------------ Google Sheets Imports ------------
import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound, APIError

# ============================================================================
# CONFIGURATION SECTION - Detailed Settings with Comments
# ============================================================================

# --- URLs Configuration ---
LOGIN_URL = "https://damadam.pk/login/"
HOME_URL = "https://damadam.pk/"
ONLINE_URL = "https://damadam.pk/online_kon/"
COOKIE_FILE = "damadam_cookies.pkl"

# --- Authentication from Environment Variables ---
USERNAME = os.getenv('DAMADAM_USERNAME', '')
PASSWORD = os.getenv('DAMADAM_PASSWORD', '')
USERNAME_2 = os.getenv('DAMADAM_USERNAME_2', '')
PASSWORD_2 = os.getenv('DAMADAM_PASSWORD_2', '')
SHEET_URL = os.getenv('GOOGLE_SHEET_URL', '')
GOOGLE_CREDENTIALS_RAW = os.getenv('GOOGLE_CREDENTIALS_JSON', '')

# --- Performance & Rate Limiting Configuration ---
# MAX_PROFILES_PER_RUN: Maximum profiles to scrape in one run (0 = unlimited)
MAX_PROFILES_PER_RUN = int(os.getenv('MAX_PROFILES_PER_RUN', '0'))
# BATCH_SIZE: Number of profiles before checking API quota
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '10'))
# MIN_DELAY & MAX_DELAY: Adaptive delay range (seconds) between requests
MIN_DELAY = float(os.getenv('MIN_DELAY', '0.5'))
MAX_DELAY = float(os.getenv('MAX_DELAY', '0.7'))
# PAGE_LOAD_TIMEOUT: Maximum time to wait for page load (seconds)
PAGE_LOAD_TIMEOUT = int(os.getenv('PAGE_LOAD_TIMEOUT', '30'))
# SHEET_WRITE_DELAY: Delay after each Google Sheets API call (seconds)
SHEET_WRITE_DELAY = float(os.getenv('SHEET_WRITE_DELAY', '1.0'))

# --- Auto-Optimization Settings ---
# After scraping 10 profiles, system auto-optimizes batch size and delays
OPTIMIZATION_SAMPLE_SIZE = 10
# Optimization factors (adjust based on performance)
BATCH_SIZE_FACTOR = 1.2  # Increase batch size by 20% if performing well
DELAY_REDUCTION_FACTOR = 0.9  # Reduce delay by 10% if performing well

# --- Column Configuration ---
# Define all columns in ProfilesData sheet
COLUMN_ORDER = [
    "IMAGE", "NICK NAME", "TAGS", "LAST POST", "LAST POST TIME", "FRIEND", "CITY",
    "GENDER", "MARRIED", "AGE", "JOINED", "FOLLOWERS", "STATUS",
    "POSTS", "PROFILE LINK", "INTRO", "SOURCE", "DATETIME SCRAP"
]
COLUMN_TO_INDEX = {name: idx for idx, name in enumerate(COLUMN_ORDER)}

# --- Highlighting Configuration ---
# ENABLE_CELL_HIGHLIGHT: Set to False to disable cell highlighting (using Notes instead)
ENABLE_CELL_HIGHLIGHT = False
# HIGHLIGHT_EXCLUDE_COLUMNS: Columns that won't be highlighted when changed
HIGHLIGHT_EXCLUDE_COLUMNS = {"LAST POST", "LAST POST TIME", "JOINED", "PROFILE LINK", "DATETIME SCRAP"}

# --- Link Columns Configuration ---
# Columns that contain URLs and need special processing
LINK_COLUMNS = {"IMAGE", "LAST POST", "PROFILE LINK"}

# --- Suspension Detection Indicators ---
# Keywords that indicate account suspension
SUSPENSION_INDICATORS = [
    "accounts suspend",
    "aik se zyada fake accounts",
    "abuse ya harassment",
    "kisi aur user ki identity apnana",
    "accounts suspend kiye",
]

# --- Sheet Names Configuration ---
PROFILES_SHEET_NAME = "ProfilesData"  # Main data sheet
RUNLIST_SHEET_NAME = "RunList"        # Task management sheet
CHECKLIST_SHEET_NAME = "CheckList"    # Tags/categories sheet
DASHBOARD_SHEET_NAME = "Dashboard"    # Metrics sheet
NICK_LIST_SHEET = "NickList"          # Nickname tracking sheet
TIMING_LOG_SHEET_NAME = "TimingLog"   # New timing records sheet

# --- RunList Columns ---
RUNLIST_HEADERS = ["Nickname", "Status", "Remarks", "Source"]

# --- CheckList Headers (formerly Tags) ---
CHECKLIST_HEADERS = ["Category", "Nicknames"]

# --- NickList Headers ---
NICK_LIST_HEADERS = ["Nick Name", "Times Seen", "First Seen", "Last Seen"]

# --- TimingLog Headers ---
TIMING_LOG_HEADERS = ["Nickname", "Timestamp", "Source", "Run Number"]

# --- Emoji Configuration ---
# Marital Status Emojis
EMOJI_MARRIED_YES = "💞"
EMOJI_MARRIED_NO = "🖤"

# Verification Status Emojis
EMOJI_VERIFIED = "🎫"
EMOJI_UNVERIFIED = "🚫"

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_pkt_time():
    """Get current time in Pakistan timezone (UTC+5)"""
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=5)

def log_msg(msg):
    """Print timestamped log message"""
    print(f"[{get_pkt_time().strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()

def column_letter(col_idx: int) -> str:
    """Convert column index to letter (0='A', 1='B', etc.)"""
    res = ""
    col_idx += 1
    while col_idx > 0:
        col_idx -= 1
        res = chr(col_idx % 26 + ord('A')) + res
        col_idx //= 26
    return res

def clean_data(v: str) -> str:
    """Clean and normalize data values"""
    if not v:
        return ""
    v = str(v).strip().replace('\xa0', ' ')
    bad = {"No city","Not set","[No Posts]","N/A","no city","not set","[no posts]","n/a","[No Post URL]","[Error]","no set","none","null","no age"}
    return "" if v in bad else re.sub(r"\s+"," ", v)

def convert_relative_date_to_absolute(text: str) -> str:
    """Convert relative dates (e.g., '2 days ago') to absolute format"""
    if not text:
        return ""
    t = text.lower().strip()
    t = t.replace("mins","minutes").replace("min","minute").replace("secs","seconds").replace("sec","second").replace("hrs","hours").replace("hr","hour")
    m = re.search(r"(\d+)\s*(second|minute|hour|day|week|month|year)s?\s*ago", t)
    if not m:
        return text
    amt = int(m.group(1)); unit = m.group(2)
    delta_map = {"second":1,"minute":60,"hour":3600,"day":86400,"week":604800,"month":2592000,"year":31536000}
    if unit in delta_map:
        dt = get_pkt_time() - timedelta(seconds=amt*delta_map[unit])
        return dt.strftime("%d-%b-%y")
    return text

def detect_suspension_reason(page: str) -> str | None:
    """Detect if account is suspended and return reason"""
    if not page:
        return None
    lower = page.lower()
    for indicator in SUSPENSION_INDICATORS:
        if indicator in lower:
            return indicator
    return None

def clean_text(text: str) -> str:
    """Clean and normalize text content"""
    if not text:
        return ""
    text = str(text).strip().replace('\xa0',' ').replace('\n',' ')
    return re.sub(r"\s+"," ", text).strip()

def parse_post_timestamp(text: str) -> str:
    """Parse post timestamp"""
    return convert_relative_date_to_absolute(text)

def to_absolute_url(href: str) -> str:
    """Convert relative URLs to absolute URLs"""
    if not href:
        return ""
    href = href.strip()
    if href.startswith('/'):
        return f"https://damadam.pk{href}"
    if not href.startswith('http'):
        return f"https://damadam.pk/{href}"
    return href

def get_friend_status(driver) -> str:
    """Check if user is a friend"""
    try:
        page_source = driver.page_source.lower()
        if 'action="/follow/remove/"' in page_source or 'unfollow.svg' in page_source:
            return "Yes"
        if 'follow.svg' in page_source and 'unfollow' not in page_source:
            return "No"
        return ""
    except Exception:
        return ""

def calculate_eta(processed: int, total: int, start_ts: float) -> str:
    """Calculate estimated time to completion"""
    if processed == 0:
        return "Calculating..."
    elapsed = time.time() - start_ts
    rate = processed / elapsed if elapsed > 0 else 0
    remaining = total - processed
    eta = remaining / rate if rate > 0 else 0
    if eta < 60:
        return f"{int(eta)}s"
    if eta < 3600:
        return f"{int(eta//60)}m {int(eta%60)}s"
    hrs = int(eta//3600); mins = int((eta%3600)//60)
    return f"{hrs}h {mins}m"

def extract_text_comment_url(href: str) -> str:
    """Extract text comment URL"""
    m = re.search(r'/comments/text/(\d+)/', href or '')
    if m:
        return to_absolute_url(f"/comments/text/{m.group(1)}/").rstrip('/')
    return to_absolute_url(href or '')

def extract_image_comment_url(href: str) -> str:
    """Extract image comment URL"""
    m = re.search(r'/comments/image/(\d+)/', href or '')
    if m:
        return to_absolute_url(f"/content/{m.group(1)}/g/")
    return to_absolute_url(href or '')

def scrape_recent_post(driver, nickname: str) -> dict:
    """Scrape the most recent post from user's profile"""
    post_url = f"https://damadam.pk/profile/public/{nickname}"
    try:
        driver.get(post_url)
        try:
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "article.mbl")))
        except TimeoutException:
            return {'LPOST': '', 'LDATE-TIME': ''}

        recent_post = driver.find_element(By.CSS_SELECTOR, "article.mbl")
        post_data = {'LPOST': '', 'LDATE-TIME': ''}

        url_selectors = [
            ("a[href*='/content/']", lambda h: to_absolute_url(h)),
            ("a[href*='/comments/text/']", extract_text_comment_url),
            ("a[href*='/comments/image/']", extract_image_comment_url),
        ]
        for selector, formatter in url_selectors:
            try:
                link = recent_post.find_element(By.CSS_SELECTOR, selector)
                href = link.get_attribute('href')
                if href:
                    formatted = formatter(href)
                    if formatted:
                        post_data['LPOST'] = formatted
                        break
            except Exception:
                continue

        time_selectors = ["span[itemprop='datePublished']", "time[itemprop='datePublished']", "span.cxs.cgy", "time"]
        for sel in time_selectors:
            try:
                time_elem = recent_post.find_element(By.CSS_SELECTOR, sel)
                if time_elem.text.strip():
                    post_data['LDATE-TIME'] = parse_post_timestamp(time_elem.text.strip())
                    break
            except Exception:
                continue
        return post_data
    except Exception:
        return {'LPOST': '', 'LDATE-TIME': ''}

# ============================================================================
# ADAPTIVE DELAY CLASS - Auto-adjusts delays based on API responses
# ============================================================================

class AdaptiveDelay:
    """
    Manages adaptive delays to avoid Google API rate limits.
    - Reduces delay on success
    - Increases delay on rate limit errors
    - Adjusts batch size based on performance
    """
    def __init__(self, mn, mx):
        self.base_min = mn
        self.base_max = mx
        self.min_delay = mn
        self.max_delay = mx
        self.hits = 0
        self.last = time.time()
        self.batch_size = BATCH_SIZE
        
    def on_success(self):
        """Called on successful API call - gradually reduce delays"""
        if self.hits:
            self.hits -= 1
        if time.time() - self.last > 10:
            self.min_delay = max(self.base_min, self.min_delay * 0.95)
            self.max_delay = max(self.base_max, self.max_delay * 0.95)
            self.last = time.time()
    
    def on_rate_limit(self):
        """Called on rate limit error - increase delays"""
        self.hits += 1
        factor = 1 + min(0.2 * self.hits, 1.0)
        self.min_delay = min(3.0, self.min_delay * factor)
        self.max_delay = min(6.0, self.max_delay * factor)
        log_msg(f"⚠️ Rate limit hit. New delays: {self.min_delay:.2f}s - {self.max_delay:.2f}s")
    
    def on_batch(self):
        """Called after batch completion - slight delay increase"""
        self.min_delay = min(3.0, max(self.base_min, self.min_delay * 1.1))
        self.max_delay = min(6.0, max(self.base_max, self.max_delay * 1.1))
    
    def optimize_batch_size(self, success_count: int):
        """Auto-optimize batch size after sample profiles"""
        if success_count >= OPTIMIZATION_SAMPLE_SIZE:
            self.batch_size = int(self.batch_size * BATCH_SIZE_FACTOR)
            self.min_delay = max(self.base_min, self.min_delay * DELAY_REDUCTION_FACTOR)
            self.max_delay = max(self.base_max, self.max_delay * DELAY_REDUCTION_FACTOR)
    
    def sleep(self):
        """Apply random delay in current range"""
        delay = random.uniform(self.min_delay, self.max_delay)
        time.sleep(delay)

# ============================================================================
# GOOGLE SHEETS CLIENT SETUP
# ============================================================================

def gsheets_client():
    """Initialize Google Sheets client"""
    try:
        creds_dict = json.loads(GOOGLE_CREDENTIALS_RAW)
        creds = Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"])
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        log_msg(f"❌ Google credentials error: {e}")
        raise

# ============================================================================
# BROWSER SETUP & LOGIN
# ============================================================================

def setup_browser():
    """Setup headless Chrome browser"""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    try:
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        return driver
    except Exception as e:
        log_msg(f"❌ Browser setup failed: {e}")
        return None

def login(driver):
    """Login to damadam.pk"""
    log_msg("🔑 Logging in...")
    try:
        driver.get(LOGIN_URL)
        time.sleep(2)
        driver.find_element(By.NAME, "email").send_keys(USERNAME)
        driver.find_element(By.NAME, "pass").send_keys(PASSWORD)
        driver.find_element(By.CSS_SELECTOR, "button[type=submit]").click()
        time.sleep(3)
        if "/login/" in driver.current_url:
            log_msg("⚠️ Primary login failed, trying secondary...")
            driver.get(LOGIN_URL)
            time.sleep(2)
            driver.find_element(By.NAME, "email").send_keys(USERNAME_2)
            driver.find_element(By.NAME, "pass").send_keys(PASSWORD_2)
            driver.find_element(By.CSS_SELECTOR, "button[type=submit]").click()
            time.sleep(3)
            if "/login/" in driver.current_url:
                log_msg("❌ Login failed")
                return False
        log_msg("✅ Login successful")
        return True
    except Exception as e:
        log_msg(f"❌ Login error: {e}")
        return False

# ============================================================================
# SHEET CLASSES
# ============================================================================

class ProfilesDataSheet:
    def __init__(self, wb):
        try:
            self.ws = wb.worksheet(PROFILES_SHEET_NAME)
        except WorksheetNotFound:
            self.ws = wb.add_worksheet(PROFILES_SHEET_NAME, 10000, len(COLUMN_ORDER))
        self.existing = {}
        self._load_existing()
        self.apply_banding()

    def _load_existing(self):
        data = self.ws.get_all_values()
        if data and data[0] == COLUMN_ORDER:
            for row_idx, row in enumerate(data[1:], start=2):
                nick = row[COLUMN_TO_INDEX["NICK NAME"]]
                if nick:
                    key = nick.lower()
                    self.existing[key] = {"row": row_idx, "data": row}

    def apply_banding(self):
        try:
            # Header formatting
            self.ws.format("A1:R1", {"backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}, "textFormat": {"bold": True}})
            # Banding for data rows only
            banding_request = {
                "addBanding": {
                    "bandedRange": {
                        "range": {"startRowIndex": 1, "endRowIndex": None, "startColumnIndex": 0, "endColumnIndex": len(COLUMN_ORDER)},
                        "rowProperties": {
                            "firstBandColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
                            "secondBandColor": {"red": 0.95, "green": 0.95, "blue": 0.95},
                        }
                    }
                }
            }
            self.ws.batch_update([banding_request])
        except Exception:
            pass

    def _update_links(self, row: int, profile: dict):
        for col_name in LINK_COLUMNS:
            url = profile.get(col_name, "")
            if url:
                col_idx = COLUMN_TO_INDEX[col_name] + 1
                formula = f'=HYPERLINK("{url}", "{col_name}")'
                self.ws.update_cell(row, col_idx, formula)

    def _add_notes(self, row: int, changed: list, before: list, after: list):
        for idx in changed:
            col = column_letter(idx)
            old = before[idx] if idx < len(before) else ""
            new = after[idx] if idx < len(after) else ""
            note = f"Changed from: {old} to {new}"
            self.ws.update_note(f"{col}{row}", note)

    def write_profile(self, profile: dict) -> dict:
        key = profile["NICK NAME"].lower()
        row_values = [profile.get(col, "") for col in COLUMN_ORDER]
        existing = self.existing.get(key)

        if existing:
            before = existing["data"]
            changed = []
            for i, (old, new) in enumerate(zip(before, row_values)):
                if old != new and COLUMN_ORDER[i] not in HIGHLIGHT_EXCLUDE_COLUMNS:
                    changed.append(i)
            # Update row values
            self.ws.update(range_name=f"A{existing['row']}:R{existing['row']}", values=[row_values])
            self._update_links(existing['row'], profile)
            if changed:
                self._add_notes(existing['row'], changed, before, row_values)
            self.existing[key]['data'] = row_values
            status = "updated" if changed else "unchanged"
            result = {"status": status, "changed_fields": [COLUMN_ORDER[i] for i in changed]}
        else:
            # New profile, append
            self.ws.append_row(row_values)
            new_row = self.ws.row_count
            self._update_links(new_row, profile)
            self.existing[key] = {'row': new_row, 'data': row_values}
            result = {"status": "new", "changed_fields": list(COLUMN_ORDER)}
        
        time.sleep(SHEET_WRITE_DELAY)
        return result

class RunListSheet:
    def __init__(self, wb):
        try:
            self.ws = wb.worksheet(RUNLIST_SHEET_NAME)
        except WorksheetNotFound:
            self.ws = wb.add_worksheet(RUNLIST_SHEET_NAME, 10000, 4)
        if not self.ws.row_values(1):
            self.ws.append_row(RUNLIST_HEADERS)
            self.ws.format("A1:D1", {"backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}, "textFormat": {"bold": True}})
        self.apply_banding()

    def apply_banding(self):
        try:
            banding_request = {
                "addBanding": {
                    "bandedRange": {
                        "range": {"startRowIndex": 1, "endRowIndex": None, "startColumnIndex": 0, "endColumnIndex": 4},
                        "rowProperties": {
                            "firstBandColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
                            "secondBandColor": {"red": 0.95, "green": 0.95, "blue": 0.95},
                        }
                    }
                }
            }
            self.ws.batch_update([banding_request])
        except Exception:
            pass

    def get_pending_nicknames(self):
        data = self.ws.get_all_values()
        return [row[0] for row in data[1:] if row and row[1].lower() == "pending"]

    def update_status(self, nickname: str, status: str, remarks: str, source: str):
        data = self.ws.get_all_values()
        for idx, row in enumerate(data[1:], start=2):
            if row[0].lower() == nickname.lower():
                self.ws.update(range_name=f"B{idx}:D{idx}", values=[[status, remarks, source]])
                time.sleep(SHEET_WRITE_DELAY)
                return
        # New entry if not found
        self.ws.append_row([nickname, status, remarks, source])
        time.sleep(SHEET_WRITE_DELAY)

class CheckListSheet:
    def __init__(self, wb):
        try:
            self.ws = wb.worksheet(CHECKLIST_SHEET_NAME)
        except WorksheetNotFound:
            self.ws = wb.add_worksheet(CHECKLIST_SHEET_NAME, 100, 2)
        if not self.ws.row_values(1):
            self.ws.append_row(CHECKLIST_HEADERS)
            self.ws.format("A1:B1", {"backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}, "textFormat": {"bold": True}})
        self.apply_banding()

    def apply_banding(self):
        try:
            banding_request = {
                "addBanding": {
                    "bandedRange": {
                        "range": {"startRowIndex": 1, "endRowIndex": None, "startColumnIndex": 0, "endColumnIndex": 2},
                        "rowProperties": {
                            "firstBandColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
                            "secondBandColor": {"red": 0.95, "green": 0.95, "blue": 0.95},
                        }
                    }
                }
            }
            self.ws.batch_update([banding_request])
        except Exception:
            pass

class DashboardSheet:
    def __init__(self, wb):
        try:
            self.ws = wb.worksheet(DASHBOARD_SHEET_NAME)
        except WorksheetNotFound:
            self.ws = wb.add_worksheet(DASHBOARD_SHEET_NAME, 20, 2)
        if not self.ws.row_values(1):
            headers = ["Metric", "Value"]
            self.ws.append_row(headers)
            self.ws.format("A1:B1", {"backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}, "textFormat": {"bold": True}})

    def get_current_run_number(self):
        data = self.ws.get_all_values()
        for row in data[1:]:
            if row and row[0] == "Run Number":
                try:
                    return int(row[1])
                except ValueError:
                    return 0
        return 0

    def update(self, metrics: dict):
        data = self.ws.get_all_values()
        existing = {row[0]: idx for idx, row in enumerate(data) if row and len(row) > 0}
        for key, value in metrics.items():
            if key in existing:
                row = existing[key] + 1
                self.ws.update_cell(row, 2, value)
            else:
                self.ws.append_row([key, value])
        time.sleep(SHEET_WRITE_DELAY)

class NickListSheet:
    def __init__(self, wb):
        try:
            self.ws = wb.worksheet(NICK_LIST_SHEET)
        except WorksheetNotFound:
            self.ws = wb.add_worksheet(NICK_LIST_SHEET, 10000, 4)
        if not self.ws.row_values(1):
            self.ws.append_row(NICK_LIST_HEADERS)
            self.ws.format("A1:D1", {"backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}, "textFormat": {"bold": True}})
        self.apply_banding()
        self.existing = self._load_existing()

    def apply_banding(self):
        try:
            banding_request = {
                "addBanding": {
                    "bandedRange": {
                        "range": {"startRowIndex": 1, "endRowIndex": None, "startColumnIndex": 0, "endColumnIndex": 4},
                        "rowProperties": {
                            "firstBandColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
                            "secondBandColor": {"red": 0.95, "green": 0.95, "blue": 0.95},
                        }
                    }
                }
            }
            self.ws.batch_update([banding_request])
        except Exception:
            pass

    def _load_existing(self):
        data = self.ws.get_all_values()
        return {row[0].lower(): {"row": idx+1, "times": int(row[1]), "first": row[2], "last": row[3]} 
                for idx, row in enumerate(data[1:]) if row and row[0]}

    def record_seen(self, nickname: str):
        now = get_pkt_time().strftime("%d-%b-%y %I:%M %p")
        key = nickname.lower()
        if key in self.existing:
            entry = self.existing[key]
            new_times = entry["times"] + 1
            self.ws.update_cell(entry["row"] + 1, 2, new_times)
            self.ws.update_cell(entry["row"] + 1, 4, now)
            self.existing[key]["times"] = new_times
            self.existing[key]["last"] = now
        else:
            new_row = [nickname, 1, now, now]
            self.ws.append_row(new_row)
            self.existing[key] = {"row": self.ws.row_count - 1, "times": 1, "first": now, "last": now}
        time.sleep(SHEET_WRITE_DELAY)

class TimingLogSheet:
    def __init__(self, wb):
        try:
            self.ws = wb.worksheet(TIMING_LOG_SHEET_NAME)
        except WorksheetNotFound:
            self.ws = wb.add_worksheet(TIMING_LOG_SHEET_NAME, 10000, 4)
        if not self.ws.row_values(1):
            self.ws.append_row(TIMING_LOG_HEADERS)
            self.ws.format("A1:D1", {"backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}, "textFormat": {"bold": True}})
        self.apply_banding()

    def apply_banding(self):
        try:
            banding_request = {
                "addBanding": {
                    "bandedRange": {
                        "range": {"startRowIndex": 1, "endRowIndex": None, "startColumnIndex": 0, "endColumnIndex": 4},
                        "rowProperties": {
                            "firstBandColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
                            "secondBandColor": {"red": 0.95, "green": 0.95, "blue": 0.95},
                        }
                    }
                }
            }
            self.ws.batch_update([banding_request])
        except Exception:
            pass

    def log_scrape(self, nickname: str, timestamp: str, source: str, run_number: int):
        row = [nickname, timestamp, source, run_number]
        self.ws.append_row(row)
        time.sleep(SHEET_WRITE_DELAY)

class Sheets:
    def __init__(self, client):
        self.wb = client.open_by_url(SHEET_URL)
        self.profiles = ProfilesDataSheet(self.wb)
        self.runlist = RunListSheet(self.wb)
        self.checklist = CheckListSheet(self.wb)
        self.dashboard = DashboardSheet(self.wb)
        self.nicklist = NickListSheet(self.wb)
        self.timinglog = TimingLogSheet(self.wb)

    def get_pending_nicknames(self):
        return self.runlist.get_pending_nicknames()

    def update_runlist_status(self, nickname: str, status: str, remarks: str, source: str):
        self.runlist.update_status(nickname, status, remarks, source)

    def write_profile(self, profile: dict) -> dict:
        return self.profiles.write_profile(profile)

    def record_nick_seen(self, nickname: str):
        self.nicklist.record_seen(nickname)

    def log_scrape(self, nickname: str, timestamp: str, source: str, run_number: int):
        self.timinglog.log_scrape(nickname, timestamp, source, run_number)

    def update_dashboard(self, metrics: dict):
        self.dashboard.update(metrics)

# ============================================================================
# SCRAPING FUNCTIONS
# ============================================================================

def fetch_online_nicknames(driver):
    """Fetch list of currently online users"""
    log_msg("👥 Fetching online users...")
    driver.get(ONLINE_URL)
    time.sleep(2)
    names = []
    try:
        items = driver.find_elements(By.CSS_SELECTOR, "li.mbl.cl.sp b")
        for b in items:
            nick = (b.text or '').strip()
            if nick and len(nick) >= 3 and any(ch.isalpha() for ch in nick):
                names.append(nick)
    except Exception:
        pass
    
    if not names:
        links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/users/']")
        for a in links:
            href = a.get_attribute('href') or ''
            if '/users/' in href:
                nick = href.split('/users/')[-1].rstrip('/')
                if nick and nick not in names and any(ch.isalpha() for ch in nick):
                    names.append(nick)
    
    log_msg(f"✅ Found {len(names)} online users")
    return names

def scrape_profile(driver, nickname: str) -> dict | None:
    """Scrape complete profile information"""
    url = f"https://damadam.pk/users/{nickname}/"
    try:
        log_msg(f"📍 Scraping: {nickname}")
        driver.get(url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1.cxl.clb.lsp")))

        page_source = driver.page_source
        now = get_pkt_time()
        suspend_reason = detect_suspension_reason(page_source)
        
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
            "DATETIME SCRAP": now.strftime("%d-%b-%y %I:%M %p"),
        }

        if suspend_reason:
            data['STATUS'] = "Suspended"
            data['INTRO'] = f"Suspended: {suspend_reason}"[:250]
            data['SUSPENSION_REASON'] = suspend_reason
            return data

        # Check verification status
        if 'account suspended' in page_source.lower():
            data['STATUS'] = f"{EMOJI_UNVERIFIED} Suspended"
        elif 'background:tomato' in page_source or 'style=\"background:tomato\"' in page_source.lower():
            data['STATUS'] = f"{EMOJI_UNVERIFIED}"
        else:
            try:
                driver.find_element(By.CSS_SELECTOR, "div[style*='tomato']")
                data['STATUS'] = f"{EMOJI_UNVERIFIED}"
            except Exception:
                data['STATUS'] = f"{EMOJI_VERIFIED}"

        data['FRIEND'] = get_friend_status(driver)

        # Extract intro
        for sel in ["span.cl.sp.lsp.nos", "span.cl", ".ow span.nos"]:
            try:
                intro = driver.find_element(By.CSS_SELECTOR, sel)
                if intro.text.strip():
                    data['INTRO'] = clean_text(intro.text)
                    break
            except Exception:
                pass

        # Extract profile fields
        fields = {'City:': 'CITY', 'Gender:': 'GENDER', 'Married:': 'MARRIED', 'Age:': 'AGE', 'Joined:': 'JOINED'}
        for label, key in fields.items():
            try:
                elem = driver.find_element(By.XPATH, f"//b[contains(text(), '{label}')]/following-sibling::span[1]")
                value = elem.text.strip()
                if not value:
                    continue
                if key == 'JOINED':
                    data[key] = convert_relative_date_to_absolute(value)
                elif key == 'GENDER':
                    low = value.lower()
                    data[key] = "💃" if 'female' in low else "👨" if 'male' in low else ""
                elif key == 'MARRIED':
                    low = value.lower()
                    if low in {'yes', 'married'}:
                        data[key] = f"{EMOJI_MARRIED_YES}"
                    elif low in {'no', 'single', 'unmarried'}:
                        data[key] = f"{EMOJI_MARRIED_NO}"
                    else:
                        data[key] = value
                else:
                    data[key] = clean_data(value)
            except Exception:
                continue

        # Extract followers
        for sel in ["span.cl.sp.clb", ".cl.sp.clb"]:
            try:
                followers = driver.find_element(By.CSS_SELECTOR, sel)
                match = re.search(r'(\d+)', followers.text)
                if match:
                    data['FOLLOWERS'] = match.group(1)
                    break
            except Exception:
                pass

        # Extract posts count
        for sel in ["a[href*='/profile/public/'] button div:first-child", "a[href*='/profile/public/'] button div"]:
            try:
                posts = driver.find_element(By.CSS_SELECTOR, sel)
                match = re.search(r'(\d+)', posts.text)
                if match:
                    data['POSTS'] = match.group(1)
                    break
            except Exception:
                pass

        # Extract image
        for sel in ["img[src*='avatar-imgs']", "img[src*='avatar']", "div[style*='whitesmoke'] img[src*='cloudfront.net']"]:
            try:
                img = driver.find_element(By.CSS_SELECTOR, sel)
                src = img.get_attribute('src')
                if src and ('avatar' in src or 'cloudfront.net' in src):
                    data['IMAGE'] = src.replace('/thumbnail/', '/')
                    break
            except Exception:
                pass

        # Extract recent post
        post_data = scrape_recent_post(driver, nickname)
        if post_data.get('LPOST'):
            data['LAST POST'] = post_data['LPOST']
        if post_data.get('LDATE-TIME'):
            data['LAST POST TIME'] = post_data['LDATE-TIME']

        return data
    except TimeoutException:
        log_msg(f"⏱️ Timeout scraping {nickname}")
        return None
    except WebDriverException as e:
        log_msg(f"🌐 Browser error scraping {nickname}: {str(e)[:50]}")
        return None
    except Exception as e:
        log_msg(f"❌ Error scraping {nickname}: {str(e)[:50]}")
        return None

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description="DamaDam Scraper")
    parser.add_argument('--limit', type=int, default=None, help='Max profiles per run (overrides .env)')
    args = parser.parse_args()

    global MAX_PROFILES_PER_RUN
    if args.limit is not None:
        MAX_PROFILES_PER_RUN = args.limit

    print("\n" + "="*80)
    print("🚀 DamaDam Master Bot v1.0.202 - Starting")
    print("="*80 + "\n")
    
    start_time = time.time()
    run_start = get_pkt_time()
    
    # Check run mode
    run_mode = os.getenv('RUN_MODE', 'online').lower()
    log_msg(f"📋 Run Mode: {run_mode.upper()}")
    
    # Initialize
    log_msg("⚙️ Initializing...")
    driver = setup_browser()
    if not driver:
        log_msg("❌ Failed to setup browser")
        return
    
    if not login(driver):
        log_msg("❌ Failed to login")
        driver.quit()
        return
    
    try:
        client = gsheets_client()
        sheets = Sheets(client)
    except Exception as e:
        log_msg(f"❌ Google Sheets error: {e}")
        driver.quit()
        return
    
    # Get run number
    run_number = sheets.dashboard.get_current_run_number() + 1
    
    # Determine which nicknames to process
    if run_mode == 'sheet':
        log_msg("📄 Reading from RunList sheet...")
        online_nicknames = sheets.get_pending_nicknames()
        if not online_nicknames:
            log_msg("⚠️ No pending nicknames in RunList")
            driver.quit()
            return
    else:
        # Fetch online users (default mode)
        try:
            online_nicknames = fetch_online_nicknames(driver)
        except Exception as e:
            log_msg(f"❌ Failed to fetch online users: {e}")
            driver.quit()
            return
        
        if not online_nicknames:
            log_msg("⚠️ No online users found")
            driver.quit()
            return
    
    # Process profiles
    log_msg(f"\n📊 Processing {len(online_nicknames)} profiles...\n")
    
    metrics = {
        "Run Number": run_number,
        "Last Run": run_start.strftime("%d-%b-%y %I:%M %p"),
        "Profiles Processed": 0,
        "Success": 0,
        "Failed": 0,
        "New Profiles": 0,
        "Updated Profiles": 0,
        "Unchanged Profiles": 0,
        "Trigger": os.getenv('GITHUB_EVENT_NAME', 'manual'),
        "Start": run_start.strftime("%d-%b-%y %I:%M %p"),
    }
    
    processed = 0
    success_count = 0
    global adaptive
    adaptive = AdaptiveDelay(MIN_DELAY, MAX_DELAY)
    
    for idx, nickname in enumerate(online_nicknames, 1):
        if MAX_PROFILES_PER_RUN > 0 and processed >= MAX_PROFILES_PER_RUN:
            log_msg(f"⏹️ Reached max profiles limit ({MAX_PROFILES_PER_RUN})")
            break
        
        # Record nickname as seen
        sheets.record_nick_seen(nickname)
        
        # Scrape profile
        profile = scrape_profile(driver, nickname)
        if not profile:
            metrics["Failed"] += 1
            if run_mode == 'sheet':
                sheets.update_runlist_status(nickname, "Failed", "Scraping error", "Online")
            log_msg(f"❌ [{idx}/{len(online_nicknames)}] Failed: {nickname}")
            adaptive.sleep()
            continue
        
        # Write to sheet
        try:
            result = sheets.write_profile(profile)
            processed += 1
            success_count += 1
            metrics["Profiles Processed"] += 1
            metrics["Success"] += 1
            
            if result["status"] == "new":
                metrics["New Profiles"] += 1
                status_mark = "✨"
            elif result["status"] == "updated":
                metrics["Updated Profiles"] += 1
                status_mark = "🔄"
            else:
                metrics["Unchanged Profiles"] += 1
                status_mark = "⏭️"
            
            log_msg(f"{status_mark} [{idx}/{len(online_nicknames)}] {result['status'].upper()}: {nickname}")
            
            # Log to TimingLog
            sheets.log_scrape(nickname, profile["DATETIME SCRAP"], profile["SOURCE"], run_number)
            
            if run_mode == 'sheet':
                sheets.update_runlist_status(nickname, "Complete", f"{result['status'].upper()}", "Online")
            
            # Auto-optimize after sample size
            if success_count == OPTIMIZATION_SAMPLE_SIZE:
                adaptive.optimize_batch_size(success_count)
            
            adaptive.on_success()
            adaptive.sleep()
        except APIError as e:
            if 'Quota exceeded' in str(e):
                adaptive.on_rate_limit()
            metrics["Failed"] += 1
            log_msg(f"❌ [{idx}/{len(online_nicknames)}] Sheet error: {nickname} - {str(e)[:50]}")
            if run_mode == 'sheet':
                sheets.update_runlist_status(nickname, "Failed", f"Sheet error: {str(e)[:50]}", "Online")
            adaptive.sleep()
        except Exception as e:
            metrics["Failed"] += 1
            log_msg(f"❌ [{idx}/{len(online_nicknames)}] Sheet error: {nickname} - {str(e)[:50]}")
            if run_mode == 'sheet':
                sheets.update_runlist_status(nickname, "Failed", f"Sheet error: {str(e)[:50]}", "Online")
            adaptive.on_rate_limit()
            adaptive.sleep()
    
    # Finalize
    metrics["End"] = get_pkt_time().strftime("%d-%b-%y %I:%M %p")
    sheets.update_dashboard(metrics)
    
    elapsed = time.time() - start_time
    
    print("\n" + "="*80)
    print("📈 RUN SUMMARY")
    print("="*80)
    print(f"Run Number:         {run_number}")
    print(f"Total Profiles:     {len(online_nicknames)}")
    print(f"Processed:          {metrics['Profiles Processed']}")
    print(f"Success:            {metrics['Success']}")
    print(f"Failed:             {metrics['Failed']}")
    print(f"New:                {metrics['New Profiles']}")
    print(f"Updated:            {metrics['Updated Profiles']}")
    print(f"Unchanged:          {metrics['Unchanged Profiles']}")
    print(f"Duration:           {int(elapsed)}s")
    print(f"Avg Time/Profile:   {elapsed/max(metrics['Success'], 1):.2f}s")
    print("="*80 + "\n")
    
    log_msg("✅ Run completed successfully")
    driver.quit()

if __name__ == "__main__":
    main()
