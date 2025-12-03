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
        
        print(f"🚀 DamaDam Master Bot v1.0.202 - Starting")
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
            
            # Get worksheets
            self.profiles_ws = self.spreadsheet.worksheet('ProfilesData')
            self.timing_ws = self._get_or_create_timing_sheet()
            
            if self.run_mode == 'sheet':
                self.runlist_ws = self.spreadsheet.worksheet('RunList')
                self.checklist_ws = self.spreadsheet.worksheet('CheckList')
            
            self.nicklist_ws = self.spreadsheet.worksheet('NickList')
            self.dashboard_ws = self.spreadsheet.worksheet('Dashboard')
            
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
        """Apply proper formatting to sheet"""
        try:
            sheet_id = worksheet._properties['sheetId']
            
            # Clear existing banding
            try:
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
            except:
                pass
            
            start_row = 1 if has_header else 0
            
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
    
    # ==================== COOKIE MANAGEMENT ====================
    
    def _save_cookies(self):
        """Save cookies to cache directory"""
        try:
            cookies = self.driver.get_cookies()
            with open(self.cookie_file, 'wb') as f:
                pickle.dump(cookies, f)
            print(f"[{self._timestamp()}] 💾 Saved {len(cookies)} cookies to cache/")
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
            
            print(f"[{self._timestamp()}] 📖 Loaded {len(cookies)} cookies from cache/")
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
            
            # Check multiple indicators
            is_logged_in = (
                'logout' in page_source or
                '/logout' in page_source or
                'login' not in current_url
            )
            
            return is_logged_in
        except:
            return False
    
    # ==================== LOGIN SYSTEM ====================
    
    def _login_with_cookies(self):
        """Try login with saved cookies"""
        print(f"[{self._timestamp()}] 🔐 Attempting login...")
        
        if not self.cookie_file.exists():
            print(f"[{self._timestamp()}] ℹ️ No saved cookies found")
            return self._login_with_credentials()
        
        try:
            print(f"[{self._timestamp()}] 📖 Found cookies, trying...")
            
            # Load homepage first
            self.driver.get('https://damadam.pk')
            time.sleep(2)
            
            # Load cookies
            if not self._load_cookies():
                return self._login_with_credentials()
            
            # Refresh to apply cookies
            self.driver.refresh()
            time.sleep(3)
            
            # Verify login
            if self._verify_login():
                print(f"[{self._timestamp()}] ✅ Login via cookies successful")
                return True
            else:
                print(f"[{self._timestamp()}] ⚠️ Cookies expired")
                self._clear_cookies()
                return self._login_with_credentials()
                
        except Exception as e:
            print(f"[{self._timestamp()}] ⚠️ Cookie login error: {e}")
            return self._login_with_credentials()
    
    def _login_with_credentials(self):
        """Try login with credentials - Account 1 then Account 2"""
        print(f"[{self._timestamp()}] 🔑 Trying credential login...")
        
        # Get credentials
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
            else:
                print(f"[{self._timestamp()}] ❌ {account_name} failed, trying next...")
        
        print(f"[{self._timestamp()}] ❌ All login attempts failed")
        return False
    
    def _attempt_login(self, username, password):
        """Attempt login with given credentials"""
        try:
            # Go to login page
            self.driver.get('https://damadam.pk/login')
            time.sleep(3)
            
            # Wait for login form
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "form"))
            )
            
            # Find username field - try multiple selectors
            username_field = None
            username_selectors = [
                "#nick",
                "input[name='nick']",
                "input[name='username']",
                "input[placeholder*='Nick']",
                "input[placeholder*='Username']"
            ]
            
            for selector in username_selectors:
                try:
                    username_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if username_field:
                        break
                except NoSuchElementException:
                    continue
            
            if not username_field:
                print(f"[{self._timestamp()}] ❌ Username field not found")
                return False
            
            # Find password field
            password_field = None
            password_selectors = [
                "#pass",
                "input[name='pass']",
                "input[name='password']",
                "input[type='password']"
            ]
            
            for selector in password_selectors:
                try:
                    password_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if password_field:
                        break
                except NoSuchElementException:
                    continue
            
            if not password_field:
                print(f"[{self._timestamp()}] ❌ Password field not found")
                return False
            
            # Find submit button
            submit_button = None
            button_selectors = [
                "button[type='submit']",
                "input[type='submit']",
                "form button",
                ".btn-login",
                ".submit-btn"
            ]
            
            for selector in button_selectors:
                try:
                    submit_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if submit_button:
                        break
                except NoSuchElementException:
                    continue
            
            if not submit_button:
                print(f"[{self._timestamp()}] ❌ Submit button not found")
                return False
            
            # Fill and submit
            username_field.clear()
            username_field.send_keys(username)
            time.sleep(0.5)
            
            password_field.clear()
            password_field.send_keys(password)
            time.sleep(0.5)
            
            submit_button.click()
            time.sleep(5)
            
            # Verify login
            return self._verify_login()
            
        except TimeoutException:
            print(f"[{self._timestamp()}] ❌ Login form timeout")
            return False
        except Exception as e:
            print(f"[{self._timestamp()}] ❌ Login error: {e}")
            return False
    
    # ==================== SCRAPING LOGIC ====================
    
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
            
            nicknames = list(set(nicknames))
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
            
            profile_data = {
                'Nickname': nickname,
                'ProfileURL': url,
                'LastUpdated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
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
                row_idx = list(self.existing_profiles.keys()).index(nickname) + 2
                values = [[v for v in profile_data.values()]]
                self.profiles_ws.update(f'A{row_idx}:Z{row_idx}', values, value_input_option='USER_ENTERED')
                status = "UPDATED"
            else:
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
