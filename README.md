# 🚀 DamaDam Master Bot v1.0.205

**Automated profile scraper for DamaDam.pk with Google Sheets integration**

[![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-Enabled-success)](https://github.com/yourusername/DD-Master-Bot/actions)
[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## ✨ What's New in v1.0.205

### 🔧 Major Fixes:
- ✅ **Fixed online user scraping** - Now correctly finds users (was returning 0)
- ✅ **Added login fallback** - Username/password login if cookies fail
- ✅ **Fixed sheet formatting** - Asimov font (row 1: size 9, row 2+: size 8)
- ✅ **Removed color formatting** - Clean, professional look
- ✅ **Fixed column ranges** - Proper ranges for all sheets
- ✅ **Enhanced error handling** - Debug HTML saved on failures

---

## 📋 Features

### Core Features
- 🔄 **Auto-Repeat Mode**: Runs indefinitely with 5-minute delay
- 👥 **Online Mode**: Scrapes currently online users automatically
- 📋 **Sheet Mode**: Processes nicknames from RunList
- ⏱️ **Timing Logs**: Tracks all scraping timestamps
- 🎯 **Profile Limits**: Manual control via command-line
- 📊 **Google Sheets**: Real-time updates with proper formatting

### Authentication
- 🍪 **Cookie-based login** (primary method)
- 🔑 **Username/password fallback** (automatic)
- 🔄 **Dual account support** (Account 1 + Account 2)

### Scheduling
- ⏰ **Automated runs**: Every 8 hours via GitHub Actions
- 🚀 **Manual runs**: On-demand with custom parameters
- 🔁 **Repeat mode**: Continuous scraping with delays

---

## 🛠️ Installation

### Local Setup

1. **Clone Repository**
   ```bash
   git clone https://github.com/yourusername/DD-Master-Bot.git
   cd DD-Master-Bot
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Setup Environment** (Create `.env` file)
   ```bash
   GOOGLE_CREDENTIALS={"type":"service_account",...}
   SHEET_URL=https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit
   DAMADAM_USERNAME=your_username
   DAMADAM_PASSWORD=your_password
   DAMADAM_USERNAME_2=backup_username  # Optional
   DAMADAM_PASSWORD_2=backup_password  # Optional
   ```

4. **Run Scraper**
   ```bash
   python Scraper.py --mode online --limit 10
   ```

---

## 🚀 Usage

### Command Line Options

**Basic Online Mode**
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

### Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--mode` | choice | `online` | Run mode: `online` or `sheet` |
| `--limit` | int | None | Max profiles to process (0 = unlimited) |
| `--repeat` | flag | False | Enable continuous running with 5-min delay |

---

## 📊 Google Sheets Structure

### ProfilesData (A:R - 18 columns)
Main sheet with all profile information:
- Nickname, ProfileURL, Image, Tags, LastPost, LastPostTime
- Friend, City, Gender, Married, Age, Joined, Followers
- Status, Posts, Intro, Source, LastUpdated

### TimingLog (A:D - 4 columns)
Timestamp tracking for each scrape:
- Nickname, Timestamp, Source, Run Number

### NickList (A:D - 4 columns)
Tracks nickname occurrences:
- Nickname, Times, FirstSeen, LastSeen

### RunList (A:E - 5 columns) [Sheet Mode Only]
Input sheet for manual scraping:
- Nickname, Status, Remarks, Tag, Priority

### CheckList (A:D - 4 columns) [Sheet Mode Only]
Tag management:
- Tag, Description, Active, Count

### Dashboard (A:K - 11 columns)
Statistics and metrics:
- Metric, Value, LastRun, TotalProfiles, OnlineUsers, etc.

---

## 🎨 Sheet Formatting

- **Font**: Asimov (row 1: size 9 bold, row 2+: size 8)
- **Alignment**: Row 1: H:Center V:Middle, Row 2+: H:Left V:Middle
- **Colors**: None (clean, professional look)

---

## 🤖 GitHub Actions Setup

### Quick Setup

1. **Add GitHub Secrets** (Settings → Secrets → Actions)
   - `GOOGLE_CREDENTIALS` - Your service account JSON
   - `SHEET_URL` - Your Google Sheets URL
   - `DAMADAM_USERNAME` - Your DamaDam username
   - `DAMADAM_PASSWORD` - Your DamaDam password
   - `DAMADAM_USERNAME_2` - Backup account (optional)
   - `DAMADAM_PASSWORD_2` - Backup password (optional)

2. **Enable Workflow**
   - Go to Actions tab
   - Enable workflows if prompted

3. **Test Run**
   - Actions → DamaDam Scraper → Run workflow
   - Mode: `online`, Limit: `10`, Repeat: ❌

📖 **Full setup guide**: See [GITHUB_SETUP.md](GITHUB_SETUP.md)

### Scheduled Runs

- **Automatic**: Every 8 hours (00:00, 08:00, 16:00 UTC)
- **Mode**: Online with repeat enabled
- **Duration**: Maximum 8 hours per run

### Manual Runs

1. Go to **Actions** → **DamaDam Scraper**
2. Click **Run workflow**
3. Select options:
   - Mode: `online` or `sheet`
   - Profile Limit: `0` (unlimited) or any number
   - Repeat Mode: ✅/❌

---

## 🔍 How It Works

### Online Mode (Default)
1. Login with cookies (or username/password fallback)
2. Fetch online users from `/online_kon/`
3. Extract nicknames using correct CSS selector
4. Scrape each profile
5. Update ProfilesData sheet (not RunList)
6. Log timing in TimingLog
7. Update NickList occurrence count
8. Wait 5 minutes (if repeat mode)
9. Repeat from step 2

### Sheet Mode
1. Login
2. Read pending nicknames from RunList
3. Scrape each profile
4. Update ProfilesData
5. Update RunList status (Done/Pending)
6. Log timing in TimingLog
7. Update NickList

---

## 🐛 Troubleshooting

### Issue: "Found 0 online users"
**Fixed in v1.0.205!** Now uses correct selector: `li.mbl.cl.sp b`

If still failing:
1. Check login was successful
2. View `debug_online_page.html` in artifacts
3. Verify you're using v1.0.205

### Issue: "Login failed"
**Solution**:
1. Check if secrets are correctly added
2. Try exporting fresh cookies from browser
3. Verify Account 1/2 credentials are correct

### Issue: "Google Sheets API error"
**Solution**:
1. Verify GOOGLE_CREDENTIALS is valid JSON
2. Check service account has edit access
3. Confirm SHEET_URL is correct

### Issue: "Cookies expired"
**Solution**: The script automatically falls back to username/password login

---

## 📝 Important Notes

### Online Mode Behavior
- ✅ Updates **ProfilesData** sheet
- ❌ Does NOT write to **RunList**
- ✅ Logs all scrapes to **TimingLog**
- ✅ Tracks occurrences in **NickList**

### Sheet Mode Behavior
- ✅ Updates **ProfilesData** sheet
- ✅ Updates **RunList** status
- ✅ Logs all scrapes to **TimingLog**
- ✅ Tracks occurrences in **NickList**

### GitHub Actions Limits
- Maximum 8-hour execution per run
- Previous runs cancelled when new run starts
- Cookies cached between runs

---

## 🔒 Security

### Protected Files (Never Commit)
- ❌ `.env` - Contains credentials
- ❌ `*.pkl` - Cookie files
- ❌ `*-master-bot-*.json` - Service account keys
- ❌ `debug_*.html` - Debug files

### GitHub Secrets
- ✅ Encrypted and secure
- ✅ Not visible in logs
- ✅ Can be updated anytime

---

## 📦 Requirements

```
selenium==4.15.2
gspread==5.12.0
google-auth==2.24.0
python-dotenv==1.0.0
webdriver-manager==4.0.1
```

---

## 📄 License

MIT License - See [LICENSE](LICENSE) file for details

---

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create feature branch
3. Commit your changes
4. Push to branch
5. Open Pull Request

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/DD-Master-Bot/issues)
- **Documentation**: [GITHUB_SETUP.md](GITHUB_SETUP.md)

---

## 🎯 Changelog

### v1.0.205 (Current)
- ✅ Fixed online user scraping (CSS selector)
- ✅ Added username/password login fallback
- ✅ Fixed sheet formatting (Asimov font)
- ✅ Removed color formatting
- ✅ Fixed column ranges for all sheets
- ✅ Enhanced error handling with debug output

### v1.0.202
- Cookie-based authentication
- Online and Sheet modes
- TimingLog tracking
- Repeat mode

---

**Version**: 1.0.205  
**Last Updated**: December 2025  
**Status**: ✅ Production Ready

---

Made with ❤️ for DamaDam automation
