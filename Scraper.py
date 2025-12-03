#!/usr/bin/env python3
"""
DamaDam Master Bot - v1.0.205 (FIXED)
- Fixed online user scraping (was returning 0)
- Added username/password login fallback
- Proper font formatting (Asimov 9/8)
- Fixed column ranges for all sheets
- Both cookie + credential login support
"""

import os
import sys
import time
import argparse
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import gspread
from google.oauth2.service_account import Credentials
import pickle
import json
import traceback
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()

class DamaDamScraper:
    def __init__(self, run_mode='online', profile_limit=None):
        self.run_mode = run_mode.lower()
        self.profile_limit = profile_limit
        self.run_number = int(time.time())
        
        print(f"🚀 DamaDam Master Bot v1.0.205 - Starting")
        print("=" * 80)
        print(f"[{self._timestamp()}] 📋 Run Mode: {self.run_mode.upper()}")
        if self.profile_limit:
            print(f"[{self._timestamp()}] 🔢 Profile Limit: {self.profile_limit}")
        print(f"[{self._timestamp()}] ⚙️ Initializing...")
        
        self.driver = None
        self.wait = None
        self.existing_profiles = {}
        self.tags = []
        self.processed_count = 0
        
        # Setup cache directory
        self.cache_dir = Path('cache')
        self.cache_dir.mkdir(exist_ok=True)
        self.cookie_file = self.cache_dir / 'damadam_cookies.pkl'
        
        # Initialize Google Sheets
        self._init_sheets()
        
    def _timestamp(self):
        return datetime.now().strftime("%H:%M:%S")
    
    def _init_sheets(self):
        """Initialize Google Sheets connection"""
        try:
            scope = ['https://spreadsheets.google.com/feeds',
                    'https://www.googleapis.com/auth/drive']
            
            creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON') or os.getenv('GOOGLE_CREDENTIALS')
            
            if not creds_json:
                raise ValueError("Missing GOOGLE_CREDENTIALS environment variable")
            
            if os.path.isfile(creds_json):
                with open(creds_json, 'r') as f:
                    creds_dict = json.load(f)
            else:
                creds_dict = json.loads(creds_json)

            credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
            self.gc = gspread.authorize(credentials)
            
            sheet_url = os.getenv('SHEET_URL') or os.getenv('GOOGLE_SHEET_URL')
            
            if not sheet_url:
                raise ValueError("Missing SHEET_URL environment variable")
            
            self.spreadsheet = self.gc.open_by_url(sheet_url)
            
            # Get or create worksheets with proper column counts
            self.profiles_ws = self._get_or_create_sheet('ProfilesData', 18)  # A:R
            self.timing_ws = self._get_or_create_sheet('TimingLog', 4)       # A:D
            
            if self.run_mode == 'sheet':
                self.runlist_ws = self._get_or_create_sheet('RunList', 5)    # A:E
                self.checklist_ws = self._get_or_create_sheet('CheckList', 4) # A:D
            
            self.nicklist_ws = self._get_or_create_sheet('NickList', 4)      # A:D
            self.dashboard_ws = self._get_or_create_sheet('Dashboard', 11)   # A:K
            
            # Apply formatting to all sheets
            self._apply_formatting()
            
            print(f"[{self._timestamp()}] ✅ Google Sheets connected")
            
        except Exception as e:
            print(f"[{self._timestamp()}] ❌ Error initializing sheets: {e}")
            print(traceback.format_exc())
            sys.exit(1)
    
    def _get_or_create_sheet(self, title, cols):
        """Get or create worksheet with specified columns"""
        try:
            ws = self.spreadsheet.worksheet(title)
            print(f"[{self._timestamp()}] ℹ️ {title} sheet found")
        except gspread.exceptions.WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(title=title, rows=1000, cols=cols)
            
            # Add headers based on sheet type
            if title == 'ProfilesData':
                headers = ['Nickname', 'ProfileURL', 'Image', 'Tags', 'LastPost', 'LastPostTime',
                          'Friend', 'City', 'Gender', 'Married', 'Age', 'Joined', 'Followers',
                          'Status', 'Posts', 'Intro', 'Source', 'LastUpdated']
            elif title == 'TimingLog':
                headers = ['Nickname', 'Timestamp', 'Source', 'Run Number']
            elif title == 'RunList':
                headers = ['Nickname', 'Status', 'Remarks', 'Tag', 'Priority']
            elif title == 'CheckList':
                headers = ['Tag', 'Description', 'Active', 'Count']
            elif title == 'NickList':
                headers = ['Nickname', 'Times', 'FirstSeen', 'LastSeen']
            elif title == 'Dashboard':
                headers = ['Metric', 'Value', 'LastRun', 'TotalProfiles', 'OnlineUsers',
                          'ProcessedToday', 'SuccessRate', 'ErrorCount', 'AvgTime', 'Status', 'Notes']
            else:
                headers = ['Column' + str(i) for i in range(1, cols + 1)]
            
            ws.update('A1:' + chr(64 + len(headers)) + '1', [headers], value_input_option='USER_ENTERED')
            print(f"[{self._timestamp()}] ✅ {title} sheet created")
        
        return ws
    
    def _apply_formatting(self):
        """Apply proper formatting to all sheets (NO COLORS, just fonts & alignment)"""
        sheets_to_format = [
            self.profiles_ws,
            self.timing_ws,
            self.nicklist_ws,
            self.dashboard_ws
        ]
        
        if self.run_mode == 'sheet':
            sheets_to_format.extend([self.runlist_ws, self.checklist_ws])
        
        for ws in sheets_to_format:
            self._format_sheet(ws)
    
    def _format_sheet(self, worksheet):
        """Apply formatting: Font Asimov 9 (row 1), 8 (row 2+), H:Middle V:Left, NO COLORS"""
        try:
            sheet_id = worksheet._properties['sheetId']
            
            requests = []
            
            # Row 1: Asimov 9, Bold, H:Center V:Middle
            requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": 1
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {
                                "fontFamily": "Asimov",
                                "fontSize": 9,
                                "bold": True
                            },
                            "horizontalAlignment": "CENTER",
                            "verticalAlignment": "MIDDLE"
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,horizontalAlignment,verticalAlignment)"
                }
            })
            
            # Row 2+: Asimov 8, H:Left V:Middle
            requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 1
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {
                                "fontFamily": "Asimov",
                                "fontSize": 8
                            },
                            "horizontalAlignment": "LEFT",
                            "verticalAlignment": "MIDDLE"
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,horizontalAlignment,verticalAlignment)"
                }
            })
            
            # Apply all formatting
            self.spreadsheet.batch_update({"requests": requests})
            print(f"[{self._timestamp()}] ✅ Formatting applied to {worksheet.title}")
            
        except Exception as e:
            print(f"[{self._timestamp()}] ⚠️ Formatting error for {worksheet.title}: {e}")
    
    def _setup_browser(self):
        """Setup Chrome browser"""
        print(f"[{self._timestamp()}] 🌐 Setting up Chrome browser...")
        
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 10)
        
        print(f"[{self._timestamp()}] ✅ Chrome ready")
    
    # ==================== COOKIE MANAGEMENT ====================
    
    def _save_cookies(self):
        """Save cookies to cache directory"""
        try:
            cookies = self.driver.get_cookies()
            with open(self.cookie_file, 'wb') as f:
                pickle.dump(cookies, f)
            print(f"[{self._timestamp()}] 💾 Saved {len(cookies)} cookies")
            return True
        except Exception as e:
            print(f"[{self._timestamp()}] ⚠️ Failed to save cookies: {e}")
            return False
    
    def _load_cookies(self):
        """Load cookies from cache directory"""
        try:
            if not self.cookie_file.exists():
                return False
            
            with open(self.cookie_file, 'rb') as f:
                cookies = pickle.load(f)
            
            for cookie in cookies:
                if 'expiry' in cookie:
                    del cookie['expiry']
                try:
                    self.driver.add_cookie(cookie)
                except:
                    pass
            
            print(f"[{self._timestamp()}] 📖 Loaded {len(cookies)} cookies")
            return True
            
        except Exception as e:
            print(f"[{self._timestamp()}] ⚠️ Cookie load failed: {e}")
            return False
    
    def _clear_cookies(self):
        """Clear expired cookies"""
        try:
            if self.cookie_file.exists():
                self.cookie_file.unlink()
                print(f"[{self._timestamp()}] 🗑️ Cleared expired cookies")
        except Exception as e:
            print(f"[{self._timestamp()}] ⚠️ Cookie clear failed: {e}")
    
    def _verify_login(self):
        """Verify if user is logged in"""
        try:
            page_source = self.driver.page_source.lower()
            current_url = self.driver.current_url.lower()
            
            is_logged_in = (
                'logout' in page_source or
                '/logout' in page_source or
                'profile' in current_url or
                'dashboard' in page_source
            )
            
            return is_logged_in
        except:
            return False
    
    # ==================== LOGIN SYSTEM (BOTH METHODS) ====================
    
    def _login_with_cookies(self):
        """Try login with saved cookies first"""
        print(f"[{self._timestamp()}] 🔐 Attempting cookie login...")
        
        if not self.cookie_file.exists():
            print(f"[{self._timestamp()}] ℹ️ No saved cookies, trying credentials...")
            return self._login_with_credentials()
        
        try:
            self.driver.get('https://damadam.pk')
            time.sleep(2)
            
            if not self._load_cookies():
                return self._login_with_credentials()
            
            self.driver.refresh()
            time.sleep(3)
            
            if self._verify_login():
                print(f"[{self._timestamp()}] ✅ Cookie login successful")
                return True
            else:
                print(f"[{self._timestamp()}] ⚠️ Cookies expired, trying credentials...")
                self._clear_cookies()
                return self._login_with_credentials()
                
        except Exception as e:
            print(f"[{self._timestamp()}] ⚠️ Cookie login error: {e}")
            return self._login_with_credentials()
    
    def _login_with_credentials(self):
        """Fallback: Login with username/password"""
        print(f"[{self._timestamp()}] 🔑 Attempting credential login...")
        
        accounts = [
            ("Account 1", os.getenv('DAMADAM_USERNAME'), os.getenv('DAMADAM_PASSWORD')),
            ("Account 2", os.getenv('DAMADAM_USERNAME_2'), os.getenv('DAMADAM_PASSWORD_2'))
        ]
        
        for account_name, username, password in accounts:
            if not username or not password:
                continue
            
            print(f"[{self._timestamp()}] 🔐 Trying {account_name}...")
            
            if self._attempt_login(username, password):
                print(f"[{self._timestamp()}] ✅ Login successful with {account_name}")
                self._save_cookies()
                return True
        
        print(f"[{self._timestamp()}] ❌ All login attempts failed")
        return False
    
    def _attempt_login(self, username, password):
        """Attempt login with credentials"""
        try:
            self.driver.get('https://damadam.pk/login')
            time.sleep(3)
            
            # Find and fill username
            username_field = self.wait.until(
                EC.presence_of_element_located((By.NAME, "nick"))
            )
            username_field.clear()
            username_field.send_keys(username)
            time.sleep(0.5)
            
            # Find and fill password
            password_field = self.driver.find_element(By.NAME, "pass")
            password_field.clear()
            password_field.send_keys(password)
            time.sleep(0.5)
            
            # Submit
            submit_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            submit_button.click()
            time.sleep(5)
            
            return self._verify_login()
            
        except Exception as e:
            print(f"[{self._timestamp()}] ❌ Login error: {e}")
            return False
    
    # ==================== SCRAPING LOGIC (FIXED) ====================
    
    def _load_existing_profiles(self):
        """Load existing profiles from ProfilesData"""
        try:
            data = self.profiles_ws.get_all_records()
            self.existing_profiles = {row['Nickname'].lower(): row for row in data if row.get('Nickname')}
            print(f"[{self._timestamp()}] 📊 Loaded {len(self.existing_profiles)} existing profiles")
        except Exception as e:
            print(f"[{self._timestamp()}] ⚠️ Error loading profiles: {e}")
    
    def _load_tags(self):
        """Load tags from CheckList"""
        if self.run_mode != 'sheet':
            return
        
        try:
            data = self.checklist_ws.get_all_values()[1:]
            self.tags = [row[0] for row in data if row and row[0]]
            print(f"[{self._timestamp()}] 🏷️ Loaded {len(self.tags)} tags")
        except Exception as e:
            print(f"[{self._timestamp()}] ⚠️ Error loading tags: {e}")
    
    def _get_nicknames_to_process(self):
        """Get list of nicknames based on run mode"""
        nicknames = []
        
        if self.run_mode == 'online':
            nicknames = self._scrape_online_users()
        elif self.run_mode == 'sheet':
            nicknames = self._get_runlist_nicknames()
        
        if self.profile_limit and self.profile_limit > 0:
            nicknames = nicknames[:self.profile_limit]
            print(f"[{self._timestamp()}] 🔢 Limited to {len(nicknames)} profiles")
        
        return nicknames
    
    def _scrape_online_users(self):
        """FIXED: Scrape currently online users"""
        try:
            print(f"[{self._timestamp()}] 🌐 Opening online users page...")
            self.driver.get('https://damadam.pk/online_kon/')
            time.sleep(4)
            
            nicknames = []
            
            # FIXED: Correct CSS selectors for DamaDam online page
            selectors = [
                'li.mbl.cl.sp b',              # Main selector from working code
                'li.mbl b',                     # Alternative
                '.online-user a',               # Backup
                'a[href*="/u/"]',               # Generic profile links
                'a[href*="/users/"]'            # Alternative URL pattern
            ]
            
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if selector == 'li.mbl.cl.sp b' or selector == 'li.mbl b':
                        # Extract text from <b> tags
                        for elem in elements:
                            nick = elem.text.strip()
                            if nick and len(nick) >= 3:
                                nicknames.append(nick)
                    else:
                        # Extract from href
                        for elem in elements:
                            href = elem.get_attribute('href')
                            if href:
                                if '/u/' in href:
                                    nick = href.split('/u/')[-1].strip('/')
                                elif '/users/' in href:
                                    nick = href.split('/users/')[-1].strip('/')
                                else:
                                    continue
                                
                                if nick and len(nick) >= 3:
                                    nicknames.append(nick)
                    
                    if nicknames:
                        break
                        
                except Exception as e:
                    continue
            
            # Remove duplicates and clean
            nicknames = list(set([n.lower() for n in nicknames if n]))
            
            print(f"[{self._timestamp()}] 👥 Found {len(nicknames)} online users")
            
            if len(nicknames) == 0:
                print(f"[{self._timestamp()}] ⚠️ WARNING: No online users found!")
                print(f"[{self._timestamp()}] 🔍 Debug: Saving page source...")
                with open('debug_online_page.html', 'w', encoding='utf-8') as f:
                    f.write(self.driver.page_source)
                print(f"[{self._timestamp()}] 💾 Saved to debug_online_page.html")
            
            return nicknames
            
        except Exception as e:
            print(f"[{self._timestamp()}] ❌ Error scraping online users: {e}")
            print(traceback.format_exc())
            return []
    
    def _get_runlist_nicknames(self):
        """Get nicknames from RunList (Sheet mode)"""
        try:
            data = self.runlist_ws.get_all_records()
            nicknames = [row['Nickname'] for row in data if row.get('Status', '').lower() == 'pending']
            print(f"[{self._timestamp()}] 📋 Found {len(nicknames)} pending nicknames in RunList")
            return nicknames
        except Exception as e:
            print(f"[{self._timestamp()}] ❌ Error reading RunList: {e}")
            return []
    
    def _scrape_profile(self, nickname):
        """Scrape a single profile"""
        try:
            url = f'https://damadam.pk/u/{nickname}'
            self.driver.get(url)
            time.sleep(2)
            
            profile_data = {
                'Nickname': nickname,
                'ProfileURL': url,
                'Image': '',
                'Tags': '',
                'LastPost': '',
                'LastPostTime': '',
                'Friend': '',
                'City': '',
                'Gender': '',
                'Married': '',
                'Age': '',
                'Joined': '',
                'Followers': '',
                'Status': '',
                'Posts': '',
                'Intro': '',
                'Source': self.run_mode,
                'LastUpdated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
            
            # Add scraping logic here for profile details
            # (This is placeholder - add real selectors)
            
            return profile_data
            
        except Exception as e:
            print(f"[{self._timestamp()}] ❌ Error scraping {nickname}: {e}")
            return None
    
    def _update_profiles_sheet(self, profile_data):
        """Update ProfilesData sheet"""
        try:
            nickname = profile_data['Nickname'].lower()
            
            # Check if profile exists
            if nickname in self.existing_profiles:
                # Update existing
                records = self.profiles_ws.get_all_records()
                for idx, row in enumerate(records, start=2):
                    if row.get('Nickname', '').lower() == nickname:
                        values = [list(profile_data.values())]
                        self.profiles_ws.update(f'A{idx}:R{idx}', values, value_input_option='USER_ENTERED')
                        status = "UPDATED"
                        break
            else:
                # Add new
                values = [list(profile_data.values())]
                self.profiles_ws.append_row(values[0], value_input_option='USER_ENTERED')
                self.existing_profiles[nickname] = profile_data
                status = "NEW"
            
            return status
            
        except Exception as e:
            print(f"[{self._timestamp()}] ❌ Error updating ProfilesData: {e}")
            return "ERROR"
    
    def _log_timing(self, nickname, source):
        """Log scraping timing to TimingLog sheet"""
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            row = [nickname, timestamp, source, self.run_number]
            self.timing_ws.append_row(row, value_input_option='USER_ENTERED')
        except Exception as e:
            print(f"[{self._timestamp()}] ⚠️ Error logging timing: {e}")
    
    def _update_nicklist(self, nickname):
        """Update NickList with occurrence count"""
        try:
            records = self.nicklist_ws.get_all_records()
            
            found = False
            for idx, row in enumerate(records, start=2):
                if row['Nickname'].lower() == nickname.lower():
                    times = int(row.get('Times', 0)) + 1
                    last_seen = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    first_seen = row.get('FirstSeen', last_seen)
                    
                    self.nicklist_ws.update(f'A{idx}:D{idx}', 
                                          [[nickname, times, first_seen, last_seen]], 
                                          value_input_option='USER_ENTERED')
                    found = True
                    break
            
            if not found:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.nicklist_ws.append_row([nickname, 1, timestamp, timestamp], 
                                           value_input_option='USER_ENTERED')
                
        except Exception as e:
            print(f"[{self._timestamp()}] ⚠️ Error updating NickList: {e}")
    
    def _update_runlist_status(self, nickname, status, remarks):
        """Update RunList status (only in sheet mode)"""
        if self.run_mode != 'sheet':
            return
            
        try:
            records = self.runlist_ws.get_all_records()
            for idx, row in enumerate(records, start=2):
                if row['Nickname'].lower() == nickname.lower():
                    self.runlist_ws.update(f'B{idx}:C{idx}', 
                                         [[status, remarks]], 
                                         value_input_option='USER_ENTERED')
                    break
        except Exception as e:
            print(f"[{self._timestamp()}] ⚠️ Error updating RunList: {e}")
    
    def run(self):
        """Main execution method"""
        try:
            self._setup_browser()
            
            if not self._login_with_cookies():
                print(f"[{self._timestamp()}] ❌ Login failed - exiting")
                return False
            
            self._load_existing_profiles()
            self._load_tags()
            
            nicknames = self._get_nicknames_to_process()
            
            if not nicknames:
                print(f"[{self._timestamp()}] ℹ️ No profiles to process")
                return True
            
            print(f"[{self._timestamp()}] 📊 Processing {len(nicknames)} profiles...")
            
            for idx, nickname in enumerate(nicknames, 1):
                print(f"[{self._timestamp()}] 📍 [{idx}/{len(nicknames)}] Scraping: {nickname}")
                
                profile_data = self._scrape_profile(nickname)
                
                if profile_data:
                    status = self._update_profiles_sheet(profile_data)
                    self._log_timing(nickname, self.run_mode)
                    self._update_nicklist(nickname)
                    
                    self.processed_count += 1
                    print(f"[{self._timestamp()}] ✅ {status}: {nickname}")
                    
                    if self.run_mode == 'sheet':
                        self._update_runlist_status(nickname, 'Done', f'{status} successfully')
                
                time.sleep(2)
            
            print(f"[{self._timestamp()}] ✅ Completed! Processed {self.processed_count} profiles")
            return True
            
        except Exception as e:
            print(f"[{self._timestamp()}] ❌ Fatal error: {e}")
            print(traceback.format_exc())
            return False
        finally:
            if self.driver:
                self.driver.quit()


def main():
    parser = argparse.ArgumentParser(description='DamaDam Profile Scraper v1.0.205')
    parser.add_argument('--mode', type=str, default='online', 
                       choices=['online', 'sheet'],
                       help='Run mode: online or sheet (default: online)')
    parser.add_argument('--limit', type=int, default=None,
                       help='Maximum number of profiles to process')
    parser.add_argument('--repeat', action='store_true',
                       help='Repeat indefinitely with 5-min delay')
    
    args = parser.parse_args()
    
    if args.repeat:
        print("🔁 Repeat mode enabled - will run indefinitely with 5-min delay")
        while True:
            scraper = DamaDamScraper(run_mode=args.mode, profile_limit=args.limit)
            scraper.run()
            
            print(f"\n⏳ Waiting 5 minutes before next run...")
            time.sleep(300)
    else:
        scraper = DamaDamScraper(run_mode=args.mode, profile_limit=args.limit)
        scraper.run()


if __name__ == '__main__':
    main()
