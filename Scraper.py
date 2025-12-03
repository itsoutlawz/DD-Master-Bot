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

# Load environment variables
load_dotenv()

class DamaDamScraper:
    def __init__(self, run_mode='online', profile_limit=None):
        self.run_mode = run_mode.lower()
        self.profile_limit = profile_limit
        self.run_number = int(time.time())  # Unique run identifier
        
        print(f"🚀 DamaDam Master Bot v1.0.201 - Starting")
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
        self.cookie_file = os.getenv('DAMADAM_COOKIE_FILE', 'damadam_cookies.pkl')

        # Initialize Google Sheets
        self._init_sheets()
        
    def _timestamp(self):
        return datetime.now().strftime("%H:%M:%S")
    
    def _init_sheets(self):
        """Initialize Google Sheets connection"""
        try:
            scope = ['https://spreadsheets.google.com/feeds',
                    'https://www.googleapis.com/auth/drive']
            
            # Try GOOGLE_CREDENTIALS_JSON first (legacy), then GOOGLE_CREDENTIALS
            creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON') or os.getenv('GOOGLE_CREDENTIALS')
            
            if not creds_json:
                raise ValueError("Missing GOOGLE_CREDENTIALS or GOOGLE_CREDENTIALS_JSON environment variable")
            
            if os.path.isfile(creds_json):
                with open(creds_json, 'r') as f:
                    creds_dict = json.load(f)
            else:
                creds_dict = json.loads(creds_json)

            credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
            self.gc = gspread.authorize(credentials)
            
            # Open the spreadsheet
            sheet_url = os.getenv('SHEET_URL') or os.getenv('GOOGLE_SHEET_URL')
            
            if not sheet_url:
                raise ValueError("Missing SHEET_URL or GOOGLE_SHEET_URL environment variable")
            
            self.spreadsheet = self.gc.open_by_url(sheet_url)
            
            # Get worksheets
            self.profiles_ws = self.spreadsheet.worksheet('ProfilesData')
            self.timing_ws = self._get_or_create_timing_sheet()
            
            # Only get RunList if in sheet mode
            if self.run_mode == 'sheet':
                self.runlist_ws = self.spreadsheet.worksheet('RunList')
                self.checklist_ws = self.spreadsheet.worksheet('CheckList')
            
            self.nicklist_ws = self.spreadsheet.worksheet('NickList')
            self.dashboard_ws = self.spreadsheet.worksheet('Dashboard')
            
            # Apply formatting to all sheets
            self._apply_consistent_formatting()
            
            print(f"[{self._timestamp()}] ✅ Google Sheets connected")
            
        except Exception as e:
            print(f"[{self._timestamp()}] ❌ Error initializing sheets: {e}")
            print(traceback.format_exc())
            sys.exit(1)
    
    def _get_or_create_timing_sheet(self):
        """Get or create TimingLog sheet"""
        try:
            ws = self.spreadsheet.worksheet('TimingLog')
            print(f"[{self._timestamp()}] ℹ️ TimingLog sheet found")
        except gspread.exceptions.WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(title='TimingLog', rows=1000, cols=4)
            # Add headers
            ws.update('A1:D1', [['Nickname', 'Timestamp', 'Source', 'Run Number']], value_input_option='USER_ENTERED')
            self._format_sheet(ws, has_header=True)
            print(f"[{self._timestamp()}] ✅ TimingLog sheet created")
        
        return ws
    
    def _apply_consistent_formatting(self):
        """Apply consistent formatting to all sheets"""
        sheets_to_format = [
            self.profiles_ws,
            self.timing_ws,
            self.nicklist_ws,
            self.dashboard_ws
        ]
        
        if self.run_mode == 'sheet':
            sheets_to_format.extend([self.runlist_ws, self.checklist_ws])
        
        for ws in sheets_to_format:
            self._format_sheet(ws, has_header=True)
    
    def _format_sheet(self, worksheet, has_header=True):
        """Apply proper formatting to sheet - banding starts from row 2"""
        try:
            sheet_id = worksheet._properties['sheetId']
            
            # Try to delete existing banding (ignore if doesn't exist)
            try:
                # Get all banding ranges
                sheet_metadata = self.spreadsheet.fetch_sheet_metadata()
                for sheet in sheet_metadata.get('sheets', []):
                    if sheet['properties']['sheetId'] == sheet_id:
                        banded_ranges = sheet.get('bandedRanges', [])
                        for banded_range in banded_ranges:
                            delete_request = {
                                "deleteBanding": {
                                    "bandedRangeId": banded_range['bandedRangeId']
                                }
                            }
                            self.spreadsheet.batch_update({"requests": [delete_request]})
                            print(f"[{self._timestamp()}] 🧹 Cleared existing banding")
            except Exception as e:
                # No banding to delete or other error - that's fine
                pass
            
            # Apply new banding (starting from row 2 to skip header)
            start_row = 1 if has_header else 0  # Row 2 in 0-indexed = 1
            
            banding_request = {
                "addBanding": {
                    "bandedRange": {
                        "bandedRangeId": sheet_id,
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": start_row,
                            "startColumnIndex": 0
                        },
                        "rowProperties": {
                            "headerColor": {
                                "red": 0.2,
                                "green": 0.5,
                                "blue": 0.8
                            },
                            "firstBandColor": {
                                "red": 0.95,
                                "green": 0.95,
                                "blue": 0.95
                            },
                            "secondBandColor": {
                                "red": 1.0,
                                "green": 1.0,
                                "blue": 1.0
                            }
                        }
                    }
                }
            }
            
            self.spreadsheet.batch_update({"requests": [banding_request]})
            
            # Format header row if exists
            if has_header:
                header_format = {
                    "requests": [{
                        "repeatCell": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": 0,
                                "endRowIndex": 1
                            },
                            "cell": {
                                "userEnteredFormat": {
                                    "backgroundColor": {
                                        "red": 0.2,
                                        "green": 0.5,
                                        "blue": 0.8
                                    },
                                    "textFormat": {
                                        "bold": True,
                                        "foregroundColor": {
                                            "red": 1.0,
                                            "green": 1.0,
                                            "blue": 1.0
                                        }
                                    },
                                    "horizontalAlignment": "CENTER"
                                }
                            },
                            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)"
                        }
                    }]
                }
                self.spreadsheet.batch_update(header_format)
            
        except Exception as e:
            print(f"[{self._timestamp()}] ⚠️ Warning: Formatting error: {e}")
    
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
    
    def _login_with_cookies(self):
        """Login using saved cookies or credentials"""
        print(f"[{self._timestamp()}] 🔐 Attempting login...")
        
        # Try cookies first
        if os.path.exists(self.cookie_file):
            print(f"[{self._timestamp()}] 📖 Found saved cookies at {self.cookie_file}, trying...")
            if self._try_cookie_login(self.cookie_file):
                return True
        
        # Fall back to username/password
        print(f"[{self._timestamp()}] 🔑 No valid cookies, trying credentials...")
        return self._login_with_credentials()
    
    def _try_cookie_login(self, cookie_file):
        """Try to login with saved cookies"""
        try:
            self.driver.get('https://damadam.pk')
            time.sleep(2)
            
            with open(cookie_file, 'rb') as f:
                cookies = pickle.load(f)
            
            for cookie in cookies:
                if 'expiry' in cookie:
                    del cookie['expiry']
                try:
                    self.driver.add_cookie(cookie)
                except:
                    pass
            
            print(f"[{self._timestamp()}] 📖 Loaded {len(cookies)} cookies")
            
            self.driver.refresh()
            time.sleep(3)
            
            # Verify login
            if "logout" in self.driver.page_source.lower() or "/logout" in self.driver.page_source.lower():
                print(f"[{self._timestamp()}] ✅ Login via cookies successful")
                return True
            else:
                print(f"[{self._timestamp()}] ⚠️ Cookies expired")
                return False
                
        except Exception as e:
            print(f"[{self._timestamp()}] ⚠️ Cookie login failed: {e}")
            return False
    
    def _login_with_credentials(self):
        """Login using username and password from environment"""
        username = os.getenv('DAMADAM_USERNAME')
        password = os.getenv('DAMADAM_PASSWORD')
        
        if not username or not password:
            print(f"[{self._timestamp()}] ❌ DAMADAM_USERNAME and DAMADAM_PASSWORD not set")
            return False
        
        try:
            self.driver.get('https://damadam.pk/login')
            time.sleep(3)
            
            # Find and fill login form
            username_field = self.wait.until(
                EC.presence_of_element_located((By.ID, "nick"))
            )
            password_field = self.wait.until(
                EC.presence_of_element_located((By.ID, "pass"))
            )
            submit_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            
            username_field.clear()
            username_field.send_keys(username)
            time.sleep(0.5)
            
            password_field.clear()
            password_field.send_keys(password)
            time.sleep(0.5)
            
            submit_button.click()
            time.sleep(5)
            
            # Verify login
            if "logout" in self.driver.page_source.lower() or "/logout" in self.driver.page_source.lower():
                print(f"[{self._timestamp()}] ✅ Login successful")
                
                # Save cookies for next time
                self._save_cookies()
                return True
            else:
                print(f"[{self._timestamp()}] ❌ Login failed - check credentials")
                return False
                
        except TimeoutException as e:
            print(f"[{self._timestamp()}] ❌ Login error: missing form field: {e}")
            return False
        except Exception as e:
            print(f"[{self._timestamp()}] ❌ Login error: {e}")
            return False
    
    def _save_cookies(self):
        """Save current session cookies"""
        try:
            cookies = self.driver.get_cookies()
            with open(self.cookie_file, 'wb') as f:
                pickle.dump(cookies, f)
            print(f"[{self._timestamp()}] 💾 Cookies saved for future use")
        except Exception as e:
            print(f"[{self._timestamp()}] ⚠️ Failed to save cookies: {e}")
    
    def _load_existing_profiles(self):
        """Load existing profiles from ProfilesData"""
        try:
            data = self.profiles_ws.get_all_records()
            self.existing_profiles = {row['Nickname']: row for row in data if row.get('Nickname')}
            print(f"[{self._timestamp()}] 📊 Loaded {len(self.existing_profiles)} existing profiles")
        except Exception as e:
            print(f"[{self._timestamp()}] ⚠️ Error loading profiles: {e}")
    
    def _load_tags(self):
        """Load tags from CheckList"""
        if self.run_mode != 'sheet':
            return
        
        try:
            data = self.checklist_ws.get_all_values()[1:]  # Skip header
            self.tags = [row[0] for row in data if row and row[0]]
            print(f"[{self._timestamp()}] 🏷️ Loaded {len(self.tags)} tags")
        except Exception as e:
            print(f"[{self._timestamp()}] ⚠️ Error loading tags: {e}")
    
    def _get_nicknames_to_process(self):
        """Get list of nicknames based on run mode"""
        nicknames = []
        
        if self.run_mode == 'online':
            # Get online users
            nicknames = self._scrape_online_users()
        elif self.run_mode == 'sheet':
            # Get from RunList
            nicknames = self._get_runlist_nicknames()
        
        # Apply profile limit if set
        if self.profile_limit and self.profile_limit > 0:
            nicknames = nicknames[:self.profile_limit]
            print(f"[{self._timestamp()}] 🔢 Limited to {len(nicknames)} profiles")
        
        return nicknames
    
    def _scrape_online_users(self):
        """Scrape currently online users"""
        try:
            self.driver.get('https://damadam.pk/online')
            time.sleep(3)
            
            nicknames = []
            user_elements = self.driver.find_elements(By.CSS_SELECTOR, '.user-card a, .online-user a')
            
            for elem in user_elements:
                href = elem.get_attribute('href')
                if href and '/u/' in href:
                    nickname = href.split('/u/')[-1].strip('/')
                    if nickname:
                        nicknames.append(nickname)
            
            nicknames = list(set(nicknames))  # Remove duplicates
            print(f"[{self._timestamp()}] 👥 Found {len(nicknames)} online users")
            
            return nicknames
            
        except Exception as e:
            print(f"[{self._timestamp()}] ❌ Error scraping online users: {e}")
            return []
    
    def _get_runlist_nicknames(self):
        """Get nicknames from RunList"""
        try:
            data = self.runlist_ws.get_all_records()
            nicknames = [row['Nickname'] for row in data if row.get('Status') == 'Pending']
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
            
            # Extract profile data (simplified)
            profile_data = {
                'Nickname': nickname,
                'ProfileURL': url,
                'LastUpdated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                # Add more fields as needed
            }
            
            return profile_data
            
        except Exception as e:
            print(f"[{self._timestamp()}] ❌ Error scraping {nickname}: {e}")
            return None
    
    def _update_profiles_sheet(self, profile_data):
        """Update ProfilesData sheet"""
        try:
            nickname = profile_data['Nickname']
            
            if nickname in self.existing_profiles:
                # Update existing
                row_idx = list(self.existing_profiles.keys()).index(nickname) + 2  # +2 for header
                values = [[v for v in profile_data.values()]]
                self.profiles_ws.update(f'A{row_idx}:Z{row_idx}', values, value_input_option='USER_ENTERED')
                status = "UPDATED"
            else:
                # Append new
                values = [[v for v in profile_data.values()]]
                self.profiles_ws.append_row(values, value_input_option='USER_ENTERED')
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
                if row['Nickname'] == nickname:
                    # Update count and timestamps
                    times = int(row.get('Times', 0)) + 1
                    last_seen = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    first_seen = row.get('FirstSeen', last_seen)
                    
                    self.nicklist_ws.update(f'A{idx}:D{idx}', 
                                          [[nickname, times, first_seen, last_seen]], 
                                          value_input_option='USER_ENTERED')
                    found = True
                    break
            
            if not found:
                # Add new entry
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.nicklist_ws.append_row([nickname, 1, timestamp, timestamp], 
                                           value_input_option='USER_ENTERED')
                
        except Exception as e:
            print(f"[{self._timestamp()}] ⚠️ Error updating NickList: {e}")
    
    def run(self):
        """Main execution method"""
        try:
            self._setup_browser()
            
            if not self._login_with_cookies():
                return False
            
            self._load_existing_profiles()
            self._load_tags()
            
            nicknames = self._get_nicknames_to_process()
            
            if not nicknames:
                print(f"[{self._timestamp()}] ℹ️ No profiles to process")
                return True
            
            print(f"[{self._timestamp()}] \n📊 Processing {len(nicknames)} profiles...")
            
            for idx, nickname in enumerate(nicknames, 1):
                print(f"[{self._timestamp()}] 📍 Scraping: {nickname}")
                
                profile_data = self._scrape_profile(nickname)
                
                if profile_data:
                    status = self._update_profiles_sheet(profile_data)
                    self._log_timing(nickname, self.run_mode)
                    self._update_nicklist(nickname)
                    
                    self.processed_count += 1
                    print(f"[{self._timestamp()}] 🔄 [{idx}/{len(nicknames)}] {status}: {nickname}")
                    
                    # Update RunList only in sheet mode
                    if self.run_mode == 'sheet':
                        self._update_runlist_status(nickname, 'Done', f'{status} successfully')
                
                time.sleep(2)  # Rate limiting
            
            print(f"[{self._timestamp()}] ✅ Completed! Processed {self.processed_count} profiles")
            return True
            
        except Exception as e:
            print(f"[{self._timestamp()}] ❌ Fatal error: {e}")
            return False
        finally:
            if self.driver:
                self.driver.quit()
    
    def _update_runlist_status(self, nickname, status, remarks):
        """Update RunList status (only in sheet mode)"""
        try:
            records = self.runlist_ws.get_all_records()
            for idx, row in enumerate(records, start=2):
                if row['Nickname'] == nickname:
                    self.runlist_ws.update(f'B{idx}:C{idx}', 
                                         [[status, remarks]], 
                                         value_input_option='USER_ENTERED')
                    break
        except Exception as e:
            print(f"[{self._timestamp()}] ⚠️ Error updating RunList: {e}")


def main():
    parser = argparse.ArgumentParser(description='DamaDam Profile Scraper')
    parser.add_argument('--mode', type=str, default='online', 
                       choices=['online', 'sheet'],
                       help='Run mode: online or sheet (default: online)')
    parser.add_argument('--limit', type=int, default=None,
                       help='Maximum number of profiles to process')
    parser.add_argument('--repeat', action='store_true',
                       help='Repeat indefinitely with 5-min delay')
    
    args = parser.parse_args()
    
    # Run once or repeat
    if args.repeat:
        print("🔁 Repeat mode enabled - will run indefinitely with 5-min delay after completion")
        while True:
            scraper = DamaDamScraper(run_mode=args.mode, profile_limit=args.limit)
            scraper.run()
            
            print(f"\n⏳ Waiting 5 minutes before next run...")
            time.sleep(300)  # 5 minutes
    else:
        scraper = DamaDamScraper(run_mode=args.mode, profile_limit=args.limit)
        scraper.run()


if __name__ == '__main__':
    main()
