# Quick Start Guide

Get DamaDam Master Bot running in 5 minutes!

## Prerequisites

- Python 3.8+
- Chrome/Chromium browser
- DamaDam.pk account
- Google Sheets account

## 1. Clone & Setup

```bash
git clone https://github.com/yourusername/DDD-Master-Bot.git
cd DDD-Master-Bot
```

## 2. Install Dependencies

```bash
pip install -r requirements.txt
```

## 3. Configure Credentials

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```
DAMADAM_USERNAME=your_username
DAMADAM_PASSWORD=your_password
GOOGLE_SHEET_URL=https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit
GOOGLE_CREDENTIALS_JSON='your_json_credentials'
```

## 4. Create Google Sheet

1. Create new Google Sheet
2. Create service account in Google Cloud Console
3. Share sheet with service account email
4. Download credentials JSON

## 5. Run

```bash
python Scraper.py
```

## What Happens

1. ✅ Browser starts
2. 🔐 Logs into DamaDam.pk
3. 👥 Fetches online users
4. 📍 Scrapes each profile
5. 📊 Writes to Google Sheet
6. ✨ Generates summary

## Output

Check your Google Sheet for:
- **ProfilesData**: All scraped profiles
- **RunList**: Task status
- **Dashboard**: Metrics
- **NickList**: Online frequency

## Troubleshooting

### Login Failed
- Verify credentials
- Check account status
- Try backup account

### Google Sheets Error
- Verify sheet URL
- Check service account access
- Validate credentials JSON

### Scraping Issues
- Check internet connection
- Increase PAGE_LOAD_TIMEOUT
- Check for account suspension

## Next Steps

- Read [README.md](README.md) for full documentation
- Check [CONTRIBUTING.md](CONTRIBUTING.md) for development
- Review [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) for details

## Support

- GitHub Issues: Report bugs
- Documentation: See README
- Examples: Check PROJECT_SUMMARY

---

**Happy Scraping!** 🚀
