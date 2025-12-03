# DamaDam Master Bot v1.0.201

Professional web scraping bot for DamaDam.pk with Google Sheets integration.

## 🎯 Features

- **Online User Scraping**: Automatically fetches and processes currently online users
- **Complete Profile Data**: Extracts 18 data points per profile including images, posts, followers, etc.
- **Google Sheets Integration**: Real-time data export with professional formatting
- **Duplicate Detection**: Automatically updates existing profiles with change tracking via notes
- **Auto-Optimization**: Intelligently adjusts batch sizes and delays after 10 profiles
- **Rate Limiting**: Adaptive delays to respect Google API quotas
- **Professional Terminal Output**: Detailed metrics and progress tracking
- **Task Management**: RunList sheet tracks scraping status (Pending/Complete)
- **Emoji Indicators**: Visual markers for verification status and marital status
- **Error Recovery**: Comprehensive error handling with detailed logging

## 📊 Data Collected

Each profile includes:
- IMAGE - Profile picture URL
- NICK NAME - Username
- TAGS - Categories/tags from CheckList
- LAST POST - URL to most recent post
- LAST POST TIME - Date of last post
- FRIEND - Friend status (Yes/No)
- CITY - Location
- GENDER - Gender (💃/🕺)
- MARRIED - Marital status (💍/❌)
- AGE - Age
- JOINED - Join date
- FOLLOWERS - Follower count
- STATUS - Account status (⬛ Verified/⬜ Unverified)
- POSTS - Total posts count
- PROFILE LINK - Direct profile URL
- INTRO - Profile bio/introduction
- SOURCE - Data source (Online)
- DATETIME SCRAP - Scraping timestamp

## 📋 Sheet Structure

### ProfilesData
Main data sheet containing all scraped profiles. Automatically sorted by scraping date (newest first).

### RunList
Task management sheet with columns:
- **Nickname**: User being processed
- **Status**: Pending/Complete/Failed
- **Remarks**: Detailed notes about scraping result
- **Source**: Data source (Online)

### CheckList
Tags and categories for profile classification.

### Dashboard
Run metrics and statistics:
- Run number and timestamp
- Profiles processed/success/failed
- New/updated/unchanged count
- Trigger type and duration

### NickList
Tracks online user appearances:
- Nickname
- Times seen
- First seen timestamp
- Last seen timestamp

## 🚀 Installation

### Prerequisites
- Python 3.8+
- Chrome/Chromium browser
- Google Sheets API credentials
- DamaDam.pk account

### Setup

1. **Clone Repository**
```bash
git clone https://github.com/yourusername/DDD-Master-Bot.git
cd DDD-Master-Bot
```

2. **Install Dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure Environment Variables**
```bash
# Create .env file
DAMADAM_USERNAME=your_username
DAMADAM_PASSWORD=your_password
DAMADAM_USERNAME_2=backup_username  # Optional
DAMADAM_PASSWORD_2=backup_password  # Optional
GOOGLE_SHEET_URL=https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit
GOOGLE_CREDENTIALS_JSON='{"type":"service_account",...}'
# OR
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json

# Optional Performance Settings
MAX_PROFILES_PER_RUN=100
BATCH_SIZE=10
MIN_DELAY=0.5
MAX_DELAY=0.7
PAGE_LOAD_TIMEOUT=30
SHEET_WRITE_DELAY=1.0
```

4. **Setup Google Sheets API**
- Go to [Google Cloud Console](https://console.cloud.google.com/)
- Create a new project
- Enable Google Sheets API
- Create a service account
- Download credentials JSON
- Share your Google Sheet with the service account email

## 🎮 Usage

### Basic Run
```bash
python Scraper.py
```

### With Environment File
```bash
export $(cat .env | xargs)
python Scraper.py
```

### Docker (Optional)
```bash
docker build -t ddd-master-bot .
docker run --env-file .env ddd-master-bot
```

## ⚙️ Configuration

### Performance Tuning

**Batch Size**: Number of profiles before API quota check
```python
BATCH_SIZE = 10  # Default
```

**Delays**: Adaptive delay between requests (seconds)
```python
MIN_DELAY = 0.5
MAX_DELAY = 0.7
```

**Auto-Optimization**: After 10 profiles, system adjusts:
```python
BATCH_SIZE_FACTOR = 1.2      # Increase by 20%
DELAY_REDUCTION_FACTOR = 0.9  # Reduce by 10%
```

### Emoji Configuration

Customize status indicators:
```python
# Marital Status
EMOJI_MARRIED = "💍"
EMOJI_MARRIED_LABEL = "💖"
EMOJI_UNMARRIED = "❌"
EMOJI_UNMARRIED_LABEL = "💔"

# Verification Status
EMOJI_VERIFIED = "⬛"
EMOJI_UNVERIFIED = "⬜"
```

## 📈 Output Example

```
================================================================================
🚀 DamaDam Master Bot v1.0.201 - Starting
================================================================================

[14:23:45] 🌐 Setting up Chrome browser...
[14:23:48] ✅ Chrome ready
[14:23:49] 🔐 Checking for saved cookies...
[14:23:52] ✅ Login via cookies successful
[14:23:53] 👥 Fetching online users...
[14:23:55] ✅ Found 45 online users

📊 Processing 45 profiles...

✨ [1/45] NEW: username1
🔄 [2/45] UPDATED: username2
⏭️ [3/45] UNCHANGED: username3
...

================================================================================
📈 RUN SUMMARY
================================================================================
Total Profiles:     45
Processed:          45
Success:            43
Failed:             2
New:                12
Updated:            18
Unchanged:          13
Duration:           234s
Avg Time/Profile:   5.44s
================================================================================

[14:28:49] ✅ Run completed successfully
```

## 🔍 Monitoring

### Check RunList Status
View the RunList sheet to see:
- Which profiles are Pending/Complete/Failed
- Detailed remarks for each profile
- Data source information

### Dashboard Metrics
Track performance in Dashboard sheet:
- Success/failure rates
- New vs updated profiles
- Processing duration
- Trigger information

### NickList Tracking
Monitor online user frequency:
- How many times each user was seen
- First and last appearance timestamps

## 🐛 Troubleshooting

### Login Issues
- Verify credentials in environment variables
- Check if account is suspended
- Try backup account (USERNAME_2/PASSWORD_2)
- Delete `damadam_cookies.pkl` to force fresh login

### Google Sheets Errors
- Verify sheet URL is correct
- Check service account has sheet access
- Ensure credentials JSON is valid
- Check API quota limits

### Scraping Failures
- Verify DamaDam.pk is accessible
- Check internet connection
- Increase PAGE_LOAD_TIMEOUT
- Check for account suspension

### Rate Limiting
- Increase MIN_DELAY and MAX_DELAY
- Reduce BATCH_SIZE
- Add delays between runs
- Check Google API quota

## 📝 Logging

Logs include timestamps and status indicators:
- ✅ Success
- ❌ Error
- ⚠️ Warning
- ℹ️ Information
- 🔄 Update
- ✨ New
- 📊 Metrics

## 🔐 Security

- Credentials stored in environment variables only
- Never commit `.env` or credentials files
- Use service account for Google Sheets
- Rotate credentials regularly
- Use separate accounts for testing/production

## 📦 Requirements

See `requirements.txt` for dependencies:
- selenium
- gspread
- google-auth-oauthlib
- google-auth-httplib2
- python-dotenv

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

MIT License - See LICENSE file

## 🙏 Support

For issues and questions:
- Check existing GitHub issues
- Review troubleshooting section
- Check logs for error details
- Contact maintainer

## 🎯 Roadmap

- [ ] Multi-threaded scraping
- [ ] Proxy support
- [ ] Advanced filtering options
- [ ] Data export formats (CSV, JSON)
- [ ] Web dashboard
- [ ] Scheduled runs
- [ ] Webhook notifications

## 📞 Contact

- GitHub: [Your GitHub Profile]
- Email: your.email@example.com

---

**Version**: 1.0.201  
**Last Updated**: 2025-11-30  
**Status**: Production Ready
