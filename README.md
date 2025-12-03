# 🚀 DamaDam Master Bot v1.0.201

Automated profile scraper for DamaDam.pk with Google Sheets integration.

## ✨ Features

- 🔄 **Auto-Repeat Mode**: Runs indefinitely with 5-minute delay after completion
- 👥 **Online Mode**: Scrapes currently online users automatically
- 📋 **Sheet Mode**: Processes nicknames from RunList sheet
- ⏱️ **Timing Logs**: Tracks all scraping timestamps in dedicated sheet
- 🎯 **Profile Limits**: Manual control via command-line or workflow
- 📊 **Google Sheets**: Real-time updates with proper formatting
- ⏰ **8-Hour Schedule**: GitHub Actions runs every 8 hours automatically

## 📋 Requirements

- Python 3.10+
- Chrome/Chromium browser
- Google Service Account with Sheets API access
- DamaDam.pk cookies (for authentication)

## 🛠️ Installation

1. **Clone Repository**
   ```bash
   git clone https://github.com/yourusername/DD-Master-Bot.git
   cd DD-Master-Bot
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Setup Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

4. **Add Cookies**
   - Login to DamaDam.pk in your browser
   - Export cookies and save as `cookies.pkl`

## 🚀 Usage

### Command Line

**Basic Online Mode (No Limit)**
```bash
python Scraper.py --mode online
```

**With Profile Limit**
```bash
python Scraper.py --mode online --limit 50
```

**Auto-Repeat Mode (Recommended)**
```bash
python Scraper.py --mode online --repeat
```

**Sheet Mode**
```bash
python Scraper.py --mode sheet --limit 100
```

### GitHub Actions (Automated)

**Scheduled Runs**
- Automatically runs every 8 hours
- Uses online mode with repeat enabled
- No profile limit (processes all online users)
- Runs for maximum 8 hours per execution

**Manual Workflow**
1. Go to Actions tab → DamaDam Scraper
2. Click "Run workflow"
3. Choose options:
   - **Mode**: online or sheet
   - **Profile Limit**: 0 = no limit
   - **Repeat Mode**: Enable for continuous running

## 📊 Google Sheets Structure

### ProfilesData
Main sheet containing all scraped profile information. Updated for both online and sheet modes.

### TimingLog (New!)
Records every scraping event with:
- Nickname
- Timestamp
- Source (online/sheet)
- Run Number (unique identifier)

### NickList
Tracks nickname occurrences:
- Nickname
- Times Seen
- First Seen
- Last Seen

### RunList (Sheet Mode Only)
Input sheet for manual scraping lists. Only used when running in sheet mode.

### Dashboard
Statistics and overview (optional).

## 🎨 Sheet Formatting

- ✅ Header row with blue background and white text
- ✅ Alternating row colors (white/light gray) starting from row 2
- ✅ Consistent formatting across all sheets
- ✅ No duplicate banding issues

## ⚙️ Configuration

### Environment Variables (.env)

```bash
# Required
GOOGLE_CREDENTIALS={"type":"service_account",...}  # JSON string or path to credentials file
SHEET_URL=https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit

# Optional
MAX_PROFILES_PER_RUN=0  # 0 = no limit
DEFAULT_MODE=online
REPEAT_DELAY_MINUTES=5
DAMADAM_COOKIE_FILE=damadam_cookies.pkl  # override the cookie cache filename/path
```

### GitHub Secrets

Set these in Repository Settings → Secrets:
- `GOOGLE_CREDENTIALS`: Your service account JSON
- `SHEET_URL`: Your Google Sheets URL

## 🔄 How It Works

### Online Mode (Default)
1. Scrapes DamaDam.pk/online page
2. Extracts all online user nicknames
3. Scrapes each profile
4. Updates **ProfilesData** only (no RunList updates)
5. Logs timing in **TimingLog**
6. Updates occurrence count in **NickList**
7. Waits 5 minutes after completion
8. Repeats (if repeat mode enabled)

### Sheet Mode
1. Reads pending nicknames from **RunList**
2. Scrapes each profile
3. Updates **ProfilesData**
4. Updates **RunList** status (Done/Pending)
5. Logs timing in **TimingLog**
6. Updates **NickList**

## 📝 Important Notes

- ⚠️ **Online mode does NOT write to RunList** (only ProfilesData)
- ⚠️ GitHub Actions has 8-hour execution limit
- ⚠️ Scheduled runs use repeat mode automatically
- ⚠️ Previous workflow runs are cancelled when new run starts
- ✅ All timing data preserved in TimingLog sheet
- ✅ Profile limit only applies to manual runs

## 🐛 Troubleshooting

**Issue: "No cookies found"**
- Solution: Add `cookies.pkl` file with valid DamaDam cookies

**Issue: "Google Sheets API error"**
- Solution: Check GOOGLE_CREDENTIALS format and permissions

**Issue: "Banding already applied"**
- Solution: Fixed! Formatting now starts from row 2

**Issue: "GitHub Actions timeout"**
- Solution: Normal after 8 hours, next run will continue

## 📄 License

MIT License - See LICENSE file for details

## 👨‍💻 Author

Your Name - DamaDam Master Bot

---

**Version**: 1.0.201  
**Last Updated**: December 2025
