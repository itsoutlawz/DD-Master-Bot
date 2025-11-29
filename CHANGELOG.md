# Changelog

All notable changes to DamaDam Master Bot are documented in this file.

## [1.0.201] - 2025-11-30

### Added
- **Master Bot**: Combined online scraping with target processing functionality
- **ProfilesData Sheet**: Unified data storage for all profiles
- **RunList Sheet**: Task management with Pending/Complete/Failed status tracking
- **CheckList Sheet**: Renamed from Tags for better organization
- **Auto-Optimization**: Intelligent batch size and delay adjustment after 10 profiles
- **Emoji Indicators**: 
  - Marital Status: 💍 (💖) for married, ❌ (💔) for unmarried
  - Verification: ⬛ for verified, ⬜ for unverified
- **Notes Instead of Highlighting**: Changed duplicate detection to use notes for changes
- **Professional Terminal Display**: Detailed metrics and progress tracking
- **URL Cleaning**: Automatic conversion of image URLs from /content/.../g/ to /comments/image/...
- **GitHub Actions**: Automated workflow for scheduled scraping
- **Comprehensive Documentation**: README, CONTRIBUTING, and CHANGELOG files
- **Environment Configuration**: .env.example for easy setup

### Changed
- **Sheet Structure**: Moved from separate ProfilesOnline/ProfilesTarget to unified ProfilesData
- **API Rate Limiting**: Improved adaptive delay system with better quota management
- **Error Handling**: More comprehensive error recovery and logging
- **Code Organization**: Better structured with detailed comments and formatting settings

### Improved
- **Performance**: Auto-tuning after 10 profiles for optimal batch sizes
- **Reliability**: Better error recovery and detailed remarks in RunList
- **User Experience**: Professional terminal output with visual indicators
- **Documentation**: Extensive inline comments explaining all configuration options

### Fixed
- Image URL formatting for consistency
- Duplicate profile detection and updates
- Google Sheets API quota handling
- Cookie management for persistent login

## [3.2.1] - Previous Version

### Features
- Online user scraping
- Profile data extraction
- Google Sheets integration
- Basic rate limiting
- NickList tracking

---

## Version History

### v1.0.201 (Current)
- Master Bot with combined functionality
- Professional terminal display
- Auto-optimization
- Emoji indicators
- Unified sheet structure

### v3.2.1 (Online Bot)
- Online user scraping
- Profile extraction
- Basic integration

### v3.2.1 (Target Bot)
- Target processing
- Profile updates
- Basic integration

---

## Upgrade Guide

### From v3.2.1 to v1.0.201

1. **Backup existing data** from ProfilesOnline and ProfilesTarget sheets
2. **Create new sheets** in your Google Sheet:
   - ProfilesData (main data)
   - RunList (task management)
   - CheckList (tags)
3. **Update environment variables** with new sheet URL if needed
4. **Run migration script** (optional) to consolidate data
5. **Update credentials** and test with sample profiles

### Breaking Changes
- Sheet names changed (ProfilesOnline → ProfilesData, Target → RunList, Tags → CheckList)
- Column structure remains the same
- API behavior improved but compatible

---

## Known Issues

- None currently known

## Future Roadmap

- [ ] Multi-threaded scraping for faster processing
- [ ] Proxy support for distributed scraping
- [ ] Advanced filtering and search options
- [ ] Data export formats (CSV, JSON, Excel)
- [ ] Web dashboard for monitoring
- [ ] Scheduled runs with cron support
- [ ] Webhook notifications for events
- [ ] Database support (PostgreSQL, MongoDB)
- [ ] REST API for external integrations
- [ ] Mobile app for monitoring

---

## Support

For issues or questions:
1. Check GitHub Issues
2. Review troubleshooting in README
3. Check logs for error details
4. Contact maintainers

---

**Latest Version**: 1.0.201  
**Release Date**: 2025-11-30  
**Status**: Production Ready
