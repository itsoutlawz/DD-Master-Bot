#!/usr/bin/env python3
"""
DamaDam Master Bot - v1.0.201
- Scrapes online users and processes them like Target Bot
- Writes all data to "ProfilesData" sheet
- Uses "RunList" for task management (Pending/Complete)
- Uses "CheckList" for tags/categories
- Professional terminal display with detailed metrics
- Auto-optimizes batch size and delays after 10 profiles
- Duplicate check with Notes instead of highlighting
- Comprehensive API rate limiting and error handling
"""

import os
import sys
import re
import time
import json
import random
from datetime import datetime, timedelta, timezone

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

# --- RunList Columns ---
RUNLIST_HEADERS = ["Nickname", "Status", "Remarks", "Source"]

# --- CheckList Headers (formerly Tags) ---
CHECKLIST_HEADERS = ["Category", "Nicknames"]

# --- NickList Headers ---
NICK_LIST_HEADERS = ["Nick Name", "Times Seen", "First Seen", "Last Seen"]

# --- Emoji Configuration ---
# Marital Status Emojis
EMOJI_MARRIED_YES = "💖"
EMOJI_MARRIED_NO = "💔"

# Verification Status Emojis
EMOJI_VERIFIED = "⬛"
EMOJI_UNVERIFIED = "⬜"

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
            log_msg(f"✅ Auto-optimized: Batch size={self.batch_size}, Delays={self.min_delay:.2f}s-{self.max_delay:.2f}s")
    
    def sleep(self):
        """Sleep with random delay within configured range"""
        time.sleep(random.uniform(self.min_delay, self.max_delay))

adaptive = AdaptiveDelay(MIN_DELAY, MAX_DELAY)

# ============================================================================
# BROWSER SETUP & AUTHENTICATION
# ============================================================================

def setup_browser():
    """Initialize Chrome browser with anti-detection settings"""
    try:
        log_msg("🌐 Setting up Chrome browser...")
        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--window-size=1920,1080")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_experimental_option('excludeSwitches', ['enable-automation'])
        opts.add_experimental_option('useAutomationExtension', False)
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        driver = webdriver.Chrome(options=opts)
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        driver.execute_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        log_msg("✅ Chrome ready")
        return driver
    except Exception as e:
        log_msg(f"❌ Browser error: {e}")
        return None

def save_cookies(driver):
    """Save browser cookies to file"""
    try:
        import pickle
        with open(COOKIE_FILE, 'wb') as f:
            pickle.dump(driver.get_cookies(), f)
        log_msg("💾 Cookies saved")
    except Exception as e:
        log_msg(f"❌ Cookie save failed: {e}")

def load_cookies(driver):
    """Load browser cookies from file"""
    try:
        import pickle, os
        if not os.path.exists(COOKIE_FILE):
            return False
        with open(COOKIE_FILE, 'rb') as f:
            cookies = pickle.load(f)
        for c in cookies:
            try:
                driver.add_cookie(c)
            except:
                pass
        log_msg(f"📖 Loaded {len(cookies)} cookies")
        return True
    except Exception as e:
        log_msg(f"❌ Cookie load failed: {e}")
        return False

def login(driver) -> bool:
    """Authenticate with DamaDam website"""
    try:
        log_msg("🔐 Checking for saved cookies...")
        driver.get(HOME_URL)
        time.sleep(2)
        if load_cookies(driver):
            driver.refresh()
            time.sleep(3)
            if 'login' not in driver.current_url.lower():
                log_msg("✅ Login via cookies successful")
                return True
            log_msg("⚠️ Cookies expired, attempting fresh login...")
        
        driver.get(LOGIN_URL)
        time.sleep(3)
        for label, u, p in [("Account 1", USERNAME, PASSWORD), ("Account 2", USERNAME_2, PASSWORD_2)]:
            if not u or not p:
                if u or p:
                    log_msg(f"⚠️ {label} incomplete (missing username or password)")
                continue
            try:
                log_msg(f"🔑 Attempting {label} login...")
                nick = WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#nick, input[name='nick']")))
                try:
                    passf = driver.find_element(By.CSS_SELECTOR, "#pass, input[name='pass']")
                except:
                    passf = WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']")))
                btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit'], form button")
                nick.clear()
                nick.send_keys(u)
                time.sleep(0.5)
                passf.clear()
                passf.send_keys(p)
                time.sleep(0.5)
                btn.click()
                time.sleep(4)
                if 'login' not in driver.current_url.lower():
                    log_msg(f"✅ {label} login successful")
                    save_cookies(driver)
                    return True
                else:
                    log_msg(f"❌ {label} login failed (still on login page)")
            except Exception as e:
                log_msg(f"❌ {label} login error: {str(e)[:50]}")
                continue
        log_msg("❌ All login attempts failed")
        return False
    except Exception as e:
        log_msg(f"❌ Login error: {e}")
        return False

# ============================================================================
# GOOGLE SHEETS MANAGEMENT
# ============================================================================

def gsheets_client():
    """Initialize Google Sheets client"""
    if not SHEET_URL:
        print("❌ GOOGLE_SHEET_URL is not set.")
        sys.exit(1)
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    gac_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '').strip()
    try:
        if gac_path and os.path.exists(gac_path):
            cred = Credentials.from_service_account_file(gac_path, scopes=scope)
        else:
            if not GOOGLE_CREDENTIALS_RAW:
                print("❌ GOOGLE_SHEET_URL is set but GOOGLE_CREDENTIALS_JSON is missing.")
                sys.exit(1)
            cred = Credentials.from_service_account_info(json.loads(GOOGLE_CREDENTIALS_RAW), scopes=scope)
        return gspread.authorize(cred)
    except Exception as e:
        print(f"❌ Google auth failed: {e}")
        sys.exit(1)

class Sheets:
    """Google Sheets management class"""
    def __init__(self, client):
        self.client = client
        self.tags_mapping = {}
        self.existing = {}
        self.nick_list_existing = {}
        self.nick_list_next_row = 2
        self.ss = client.open_by_url(SHEET_URL)
        
        # Initialize ProfilesData sheet
        self.ws = self._get_or_create(PROFILES_SHEET_NAME, cols=len(COLUMN_ORDER))
        
        # Initialize RunList sheet
        self.runlist = self._get_or_create(RUNLIST_SHEET_NAME, cols=4)
        
        # Initialize CheckList sheet (formerly Tags)
        self.checklist = self._get_sheet_if_exists(CHECKLIST_SHEET_NAME)
        
        # Initialize Dashboard sheet
        self.dashboard = self._get_or_create(DASHBOARD_SHEET_NAME, cols=11)
        
        # Initialize NickList sheet
        self.nick_list_ws = self._get_or_create(NICK_LIST_SHEET, cols=len(NICK_LIST_HEADERS))
        
        # Setup headers
        self._setup_headers()
        self._format()
        self._load_existing()
        self._load_tags_mapping()
        self._ensure_nick_list()

    def _get_or_create(self, name, cols=20, rows=1000):
        """Get existing sheet or create new one"""
        try:
            return self.ss.worksheet(name)
        except WorksheetNotFound:
            return self.ss.add_worksheet(title=name, rows=rows, cols=cols)

    def _get_sheet_if_exists(self, name):
        """Get sheet if it exists, return None otherwise"""
        try:
            return self.ss.worksheet(name)
        except WorksheetNotFound:
            log_msg(f"ℹ️ {name} sheet not found, skipping optional features")
            return None

    def _setup_headers(self):
        """Initialize sheet headers"""
        try:
            # ProfilesData headers
            values = self.ws.get_all_values()
            if not values or not values[0] or all(not c for c in values[0]):
                log_msg("📋 Initializing ProfilesData headers...")
                self.ws.append_row(COLUMN_ORDER)
                try:
                    self.ws.freeze(rows=1)
                except:
                    pass
        except Exception as e:
            log_msg(f"❌ ProfilesData header init failed: {e}")

        try:
            # RunList headers
            rvals = self.runlist.get_all_values()
            if not rvals or not rvals[0] or all(not c for c in rvals[0]):
                log_msg("📋 Initializing RunList headers...")
                self.runlist.append_row(RUNLIST_HEADERS)
        except Exception as e:
            log_msg(f"❌ RunList header init failed: {e}")

        try:
            # CheckList headers
            if self.checklist:
                cvals = self.checklist.get_all_values()
                if not cvals or not cvals[0] or all(not c for c in cvals[0]):
                    log_msg("📋 Initializing CheckList headers...")
                    self.checklist.append_row(CHECKLIST_HEADERS)
        except Exception as e:
            log_msg(f"❌ CheckList header init failed: {e}")

        try:
            # NickList headers
            nvals = self.nick_list_ws.get_all_values()
            if not nvals or not nvals[0] or all(not c for c in nvals[0]):
                log_msg("📋 Initializing NickList headers...")
                self.nick_list_ws.append_row(NICK_LIST_HEADERS)
        except Exception as e:
            log_msg(f"❌ NickList header init failed: {e}")

        try:
            # Dashboard headers
            dvals = self.dashboard.get_all_values()
            expected = ["Run#", "Timestamp", "Profiles", "Success", "Failed", "New", "Updated", "Unchanged", "Trigger", "Start", "End"]
            if not dvals or dvals[0] != expected:
                self.dashboard.clear()
                self.dashboard.append_row(expected)
        except Exception as e:
            log_msg(f"❌ Dashboard header init failed: {e}")

    def _apply_banding(self, sheet, end_col, start_row=1):
    """Apply alternating row colors to sheet (custom colors)"""
    try:
        end_col = max(end_col, 1)

        req = {
            "addBanding": {
                "bandedRange": {
                    "range": {
                        "sheetId": sheet.id,
                        "startRowIndex": start_row,
                        "startColumnIndex": 0,
                        "endColumnIndex": end_col,
                    },
                    "rowProperties": {
                        # Header row color (Dark Red #cc0000)
                        "headerColor": {
                            "red": 0.8,   # 204/255
                            "green": 0.0,
                            "blue": 0.0
                        },

                        # First band (White)
                        "firstBandColor": {
                            "red": 1.0,
                            "green": 1.0,
                            "blue": 1.0
                        },

                        # Second band (Very light #ffe8e8)
                        "secondBandColor": {
                            "red": 1.0,   # 10% of 204
                            "green": 0.91,
                            "blue": 0.91
                        },
                    },
                }
            }
        }

        self.ss.batch_update({"requests": [req]})

    except APIError as e:
        message = str(e)
        if "already has alternating background colors" in message:
            log_msg(f"ℹ️ Banding already applied on {sheet.title}")
        else:
            log_msg(f"❌ Banding failed: {e}")

    def _format(self):
        """Format all sheets with professional styling"""
        try:
            # ProfilesData formatting
            self.ws.format("A:R", {"textFormat": {"fontFamily": "Courier New", "fontSize": 8, "bold": False}})
            self.ws.format("A1:R1", {"textFormat": {"fontFamily": "Courier New", "fontSize": 9, "bold": True}, "horizontalAlignment": "CENTER", "backgroundColor": {"red": 1.0, "green": 0.6, "blue": 0.0}})
            try:
                self.ws.freeze(rows=1)
            except:
                pass
            self._apply_banding(self.ws, len(COLUMN_ORDER), start_row=1)
            try:
                self.ws.sort((18, "des"), range="A1:R")
            except:
                pass
        except Exception as e:
            log_msg(f"❌ ProfilesData format failed: {e}")

        try:
            # RunList formatting
            self.runlist.format("A:D", {"textFormat": {"fontFamily": "Courier New", "fontSize": 8, "bold": False}})
            self.runlist.format("A1:D1", {"textFormat": {"fontFamily": "Courier New", "fontSize": 9, "bold": True}, "horizontalAlignment": "CENTER", "backgroundColor": {"red": 1.0, "green": 0.6, "blue": 0.0}})
            try:
                self.runlist.freeze(rows=1)
            except:
                pass
            self._apply_banding(self.runlist, 4, start_row=1)
        except Exception as e:
            log_msg(f"❌ RunList format failed: {e}")

        try:
            # CheckList formatting
            if self.checklist:
                self.checklist.format("A:B", {"textFormat": {"fontFamily": "Courier New", "fontSize": 8, "bold": False}})
                self.checklist.format("A1:B1", {"textFormat": {"fontFamily": "Courier New", "fontSize": 9, "bold": True}, "horizontalAlignment": "CENTER", "backgroundColor": {"red": 1.0, "green": 0.6, "blue": 0.0}})
                try:
                    self.checklist.freeze(rows=1)
                except:
                    pass
                self._apply_banding(self.checklist, 2, start_row=1)
        except Exception as e:
            log_msg(f"❌ CheckList format failed: {e}")

        try:
            # NickList formatting
            self.nick_list_ws.format("A:D", {"textFormat": {"fontFamily": "Courier New", "fontSize": 8, "bold": False}})
            self.nick_list_ws.format("A1:D1", {"textFormat": {"fontFamily": "Courier New", "fontSize": 9, "bold": True}, "horizontalAlignment": "CENTER", "backgroundColor": {"red": 1.0, "green": 0.6, "blue": 0.0}})
            try:
                self.nick_list_ws.freeze(rows=1)
            except:
                pass
            self._apply_banding(self.nick_list_ws, 4, start_row=1)
        except Exception as e:
            log_msg(f"❌ NickList format failed: {e}")

        try:
            # Dashboard formatting
            self.dashboard.format("A:K", {"textFormat": {"fontFamily": "Courier New", "fontSize": 8, "bold": False}})
            self.dashboard.format("A1:K1", {"textFormat": {"fontFamily": "Courier New", "fontSize": 9, "bold": True}, "horizontalAlignment": "CENTER", "backgroundColor": {"red": 1.0, "green": 0.6, "blue": 0.0}})
            try:
                self.dashboard.freeze(rows=1)
            except:
                pass
            self._apply_banding(self.dashboard, self.dashboard.col_count, start_row=1)
            try:
                self.dashboard.sort((2, "des"), range="A1:K")
            except:
                pass
        except Exception as e:
            log_msg(f"❌ Dashboard format failed: {e}")

    def _load_existing(self):
        """Load existing profiles from ProfilesData sheet"""
        try:
            self.existing = {}
            rows = self.ws.get_all_values()[1:]
            for i, r in enumerate(rows, start=2):
                if len(r) > 1 and r[1].strip():
                    self.existing[r[1].strip().lower()] = {'row': i, 'data': r}
            log_msg(f"📊 Loaded {len(self.existing)} existing profiles")
        except Exception as e:
            log_msg(f"❌ Load existing failed: {e}")

    def _load_tags_mapping(self):
        """Load tags/categories from CheckList sheet"""
        self.tags_mapping = {}
        if not self.checklist:
            return
        try:
            all_values = self.checklist.get_all_values()
            if not all_values or len(all_values) < 2:
                return
            headers = all_values[0]
            for col_idx, header in enumerate(headers):
                tag_name = clean_data(header)
                if not tag_name:
                    continue
                for row in all_values[1:]:
                    if col_idx < len(row):
                        nickname = row[col_idx].strip()
                        if nickname:
                            key = nickname.lower()
                            if key in self.tags_mapping:
                                if tag_name not in self.tags_mapping[key]:
                                    self.tags_mapping[key] += f", {tag_name}"
                            else:
                                self.tags_mapping[key] = tag_name
            log_msg(f"🏷️ Loaded {len(self.tags_mapping)} tags")
        except Exception as e:
            log_msg(f"❌ Tags load failed: {e}")

    def _ensure_nick_list(self):
        """Initialize NickList sheet"""
        try:
            values = self.nick_list_ws.get_all_values()
            headers_present = values[0] if values else []
            if headers_present[:len(NICK_LIST_HEADERS)] != NICK_LIST_HEADERS:
                self.nick_list_ws.clear()
                self.nick_list_ws.append_row(NICK_LIST_HEADERS)
                values = self.nick_list_ws.get_all_values()
            self.nick_list_next_row = len(values) + 1 if values else 2
        except Exception as e:
            log_msg(f"❌ Nick list init failed: {e}")
            self.nick_list_ws = None
            return
        self._load_nick_list()

    def _load_nick_list(self):
        """Load existing nicknames from NickList sheet"""
        if not getattr(self, 'nick_list_ws', None):
            return
        self.nick_list_existing = {}
        try:
            values = self.nick_list_ws.get_all_values()
            for idx, row in enumerate(values[1:], start=2):
                nickname = (row[0] if len(row) > 0 else '').strip()
                if not nickname:
                    continue
                times_seen = row[1].strip() if len(row) > 1 else ""
                first_seen = row[2].strip() if len(row) > 2 else ""
                last_seen = row[3].strip() if len(row) > 3 else ""
                try:
                    times_val = int(times_seen)
                except Exception:
                    times_val = 0
                self.nick_list_existing[nickname.lower()] = {
                    "row": idx,
                    "times": times_val,
                    "first": first_seen,
                    "last": last_seen,
                }
            self.nick_list_next_row = len(values) + 1 if values else 2
        except Exception as e:
            log_msg(f"❌ Nick list load failed: {e}")

    def record_nick_seen(self, nickname: str, seen_at: datetime | None = None):
        """Record that a nickname was seen online"""
        if not nickname:
            return
        if not getattr(self, 'nick_list_ws', None):
            return
        seen_at = seen_at or get_pkt_time()
        ts = seen_at.strftime("%d-%b-%y %I:%M %p")
        key = nickname.strip().lower()
        if not key:
            return
        entry = self.nick_list_existing.get(key)
        if entry:
            times = entry['times'] + 1
            first_seen = entry['first'] or ts
            last_seen = ts
            row = entry['row']
            try:
                self.nick_list_ws.update(range_name=f"A{row}:D{row}", values=[[nickname, str(times), first_seen, last_seen]], value_input_option='USER_ENTERED')
                time.sleep(SHEET_WRITE_DELAY)
            except Exception as e:
                log_msg(f"⚠️ Nick update skipped (quota): {nickname}")
                return
            entry['times'] = times
            entry['last'] = last_seen
        else:
            first_seen = ts
            last_seen = ts
            row = self.nick_list_next_row
            try:
                self.nick_list_ws.append_row([nickname, "1", first_seen, last_seen])
                time.sleep(SHEET_WRITE_DELAY)
            except Exception as e:
                log_msg(f"⚠️ Nick append skipped (quota): {nickname}")
                return
            self.nick_list_existing[key] = {
                "row": row,
                "times": 1,
                "first": first_seen,
                "last": last_seen,
            }
            self.nick_list_next_row += 1

    def update_runlist_status(self, nickname: str, status: str, remarks: str, source: str):
        """Update RunList with task status"""
        try:
            # Find existing row
            rows = self.runlist.get_all_values()[1:]
            for i, r in enumerate(rows, start=2):
                if len(r) > 0 and r[0].lower() == nickname.lower():
                    self.runlist.update(range_name=f"A{i}:D{i}", values=[[nickname, status, remarks, source]], value_input_option='USER_ENTERED')
                    time.sleep(SHEET_WRITE_DELAY)
                    return
            # Add new row if not found
            self.runlist.append_row([nickname, status, remarks, source])
            time.sleep(SHEET_WRITE_DELAY)
        except Exception as e:
            log_msg(f"⚠️ RunList update failed: {e}")

    def get_pending_nicknames(self):
        """Get nicknames with 'Pending' status from RunList"""
        try:
            rows = self.runlist.get_all_values()
            pending_nicks = []
            
            # Find Status column (column B, index 1)
            if not rows or len(rows) < 2:
                log_msg("⚠️ RunList is empty")
                return []
            
            headers = rows[0]
            status_col_idx = -1
            nickname_col_idx = -1
            
            # Find column indices
            for idx, header in enumerate(headers):
                if header.lower() == 'status':
                    status_col_idx = idx
                elif header.lower() == 'nickname':
                    nickname_col_idx = idx
            
            if status_col_idx == -1 or nickname_col_idx == -1:
                log_msg("❌ RunList missing Status or Nickname column")
                return []
            
            # Extract pending nicknames
            for row in rows[1:]:
                if len(row) > status_col_idx and len(row) > nickname_col_idx:
                    status = row[status_col_idx].strip().lower()
                    nickname = row[nickname_col_idx].strip()
                    
                    # Only pick nicks with "Pending" status
                    if status == 'pending' and nickname:
                        pending_nicks.append(nickname)
            
            log_msg(f"📋 Found {len(pending_nicks)} pending nicknames in RunList")
            return pending_nicks
        except Exception as e:
            log_msg(f"❌ Failed to get pending nicknames: {e}")
            return []

    def update_dashboard(self, metrics: dict):
        """Update Dashboard with run metrics"""
        try:
            row = [
                metrics.get("Run Number", 1),
                metrics.get("Last Run", get_pkt_time().strftime("%d-%b-%y %I:%M %p")),
                metrics.get("Profiles Processed", 0),
                metrics.get("Success", 0),
                metrics.get("Failed", 0),
                metrics.get("New Profiles", 0),
                metrics.get("Updated Profiles", 0),
                metrics.get("Unchanged Profiles", 0),
                metrics.get("Trigger", os.getenv('GITHUB_EVENT_NAME', 'manual')),
                metrics.get("Start", get_pkt_time().strftime("%d-%b-%y %I:%M %p")),
                metrics.get("End", get_pkt_time().strftime("%d-%b-%y %I:%M %p")),
            ]
            self.dashboard.append_row(row)
        except Exception as e:
            log_msg(f"❌ Dashboard update failed: {e}")

    def _clean_url(self, url):
        """Clean image URLs: convert /content/.../g/ to /comments/image/..."""
        if not url or not isinstance(url, str):
            return url
        # Convert /content/.../g/ to /comments/image/...
        if '/content/' in url and '/g/' in url:
            try:
                # Extract the ID
                id_part = url.split('/content/')[-1].split('/')[0]
                return f'https://damadam.pk/comments/image/{id_part}'
            except (IndexError, AttributeError):
                return url
        return url

    def _update_links(self, row_idx, data):
        """Update URL columns with raw URLs (no formulas)"""
        for col in LINK_COLUMNS:
            try:
                v = data.get(col)
                if not v:
                    continue
                # Clean the URL if it's an image URL
                if col == 'LAST POST' and v and isinstance(v, str) and '/content/' in v and '/g/' in v:
                    v = self._clean_url(v)
                c = COLUMN_TO_INDEX[col]
                cell = f"{column_letter(c)}{row_idx}"
                # Store raw URL instead of formula
                self.ws.update(values=[[v]], range_name=cell, value_input_option='USER_ENTERED')
                time.sleep(SHEET_WRITE_DELAY)
            except Exception as e:
                log_msg(f"⚠️ Link update skipped (quota): {col}")
                continue

    def _add_notes(self, row_idx, indices, before, new_vals):
        """Add notes to changed cells instead of highlighting"""
        if not indices:
            return
        reqs = []
        for idx in indices:
            note = f"Before: {before.get(COLUMN_ORDER[idx], '')}\nAfter: {new_vals[idx]}"
            reqs.append({
                "updateCells": {
                    "range": {
                        "sheetId": self.ws.id,
                        "startRowIndex": row_idx - 1,
                        "endRowIndex": row_idx,
                        "startColumnIndex": idx,
                        "endColumnIndex": idx + 1
                    },
                    "rows": [{"values": [{"note": note}]}],
                    "fields": "note"
                }
            })
        if reqs:
            self.ss.batch_update({"requests": reqs})

    def write_profile(self, profile: dict):
        """Write profile to ProfilesData sheet"""
        nickname = (profile.get("NICK NAME") or "").strip()
        if not nickname:
            return {"status": "error", "error": "Missing nickname", "changed_fields": []}
        
        # Normalize data
        if profile.get("LAST POST TIME"):
            profile["LAST POST TIME"] = convert_relative_date_to_absolute(profile["LAST POST TIME"])
        profile["DATETIME SCRAP"] = get_pkt_time().strftime("%d-%b-%y %I:%M %p")
        
        nickname_lower = nickname.lower()
        tags_value = self.tags_mapping.get(nickname_lower)
        if tags_value:
            profile["TAGS"] = tags_value
        
        # Build row values
        row_values = []
        for c in COLUMN_ORDER:
            if c == "IMAGE":
                v = ""
            elif c == "PROFILE LINK":
                v = profile.get(c) or ""
            elif c == "LAST POST":
                v = profile.get(c) or ""
            else:
                v = clean_data(profile.get(c, ""))
            row_values.append(v)
        
        key = nickname_lower
        existing = self.existing.get(key)
        
        if existing:
            # Update existing profile
            before = {COLUMN_ORDER[i]: (existing['data'][i] if i < len(existing['data']) else "") for i in range(len(COLUMN_ORDER))}
            changed = []
            for i, col in enumerate(COLUMN_ORDER):
                if col in HIGHLIGHT_EXCLUDE_COLUMNS:
                    continue
                old = before.get(col, "") or ""
                new = row_values[i] or ""
                if old != new:
                    changed.append(i)
            
            # Insert at row 2
            self.ws.insert_row(row_values, 2)
            self._update_links(2, profile)
            
            if changed:
                # Add notes instead of highlighting
                self._add_notes(2, changed, before, row_values)
            
            # Delete old row
            try:
                old_row = existing['row'] + 1 if existing['row'] >= 2 else 3
                self.ws.delete_rows(old_row)
            except Exception as e:
                log_msg(f"❌ Old row delete failed: {e}")
            
            self.existing[key] = {'row': 2, 'data': row_values}
            status = "updated" if changed else "unchanged"
            result = {"status": status, "changed_fields": [COLUMN_ORDER[i] for i in changed]}
        else:
            # New profile
            self.ws.insert_row(row_values, 2)
            self._update_links(2, profile)
            self.existing[key] = {'row': 2, 'data': row_values}
            result = {"status": "new", "changed_fields": list(COLUMN_ORDER)}
        
        time.sleep(SHEET_WRITE_DELAY)
        return result

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
        elif 'background:tomato' in page_source or 'style="background:tomato"' in page_source.lower():
            data['STATUS'] = f"{EMOJI_UNVERIFIED} Unverified"
        else:
            try:
                driver.find_element(By.CSS_SELECTOR, "div[style*='tomato']")
                data['STATUS'] = f"{EMOJI_UNVERIFIED} Unverified"
            except Exception:
                data['STATUS'] = f"{EMOJI_VERIFIED} Verified"

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
                    data[key] = "💃" if low == 'female' else "🕺" if low == 'male' else value
                elif key == 'MARRIED':
                    low = value.lower()
                    if low in {'yes', 'married'}:
                        data[key] = f"Yes={EMOJI_MARRIED_YES}"
                    elif low in {'no', 'single', 'unmarried'}:
                        data[key] = f"No={EMOJI_MARRIED_NO}"
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
    print("\n" + "="*80)
    print("🚀 DamaDam Master Bot v1.0.201 - Starting")
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
        "Run Number": 1,
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
            sheets.update_runlist_status(nickname, "Complete", f"{result['status'].upper()}", "Online")
            
            # Auto-optimize after sample size
            if success_count == OPTIMIZATION_SAMPLE_SIZE:
                adaptive.optimize_batch_size(success_count)
            
            adaptive.on_success()
            adaptive.sleep()
        except Exception as e:
            metrics["Failed"] += 1
            log_msg(f"❌ [{idx}/{len(online_nicknames)}] Sheet error: {nickname} - {str(e)[:50]}")
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

