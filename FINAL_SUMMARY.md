# Google Maps Scraper - Final Summary

## ✅ What You Have

Two powerful scrapers that work the same way:

### 1. `scraper.py` - Keyword + Location
For searching by business type and location
```bash
python scraper.py --keyword "gym" --location "Miami"
```

### 2. `scraper_by_link.py` - Google Maps Links
For scraping from existing Google Maps URLs
```bash
python scraper_by_link.py
# Then paste: https://www.google.com/maps/search/gym+in+Miami/
```

## 🎯 Features (Both Scrapers)

✅ **Email Scraping**
- Scrapes emails from Google Maps listings
- Visits business websites to find emails
- Checks contact pages automatically
- **Filters out fake emails** (test@, demo@, sample@, etc.)

✅ **Complete Data**
- Name, address, coordinates
- Phone, email, website
- Rating, hours, price level
- Category, business status

✅ **Speed Optimized**
- ~30-40 seconds per business
- 50 businesses in ~25-35 minutes
- Smart timeouts and delays

✅ **Smart Features**
- Proxy rotation (10 proxies loaded)
- Anti-bot detection
- Duplicate removal
- Progress tracking
- Incremental saving

## ⚙️ Default Settings

- **Max results**: 50 (can change with --max)
- **Headless**: Yes (runs in background)
- **Email scraping**: Enabled
- **Proxy file**: proxies.txt (10 proxies loaded)

## 📊 Output Files

Both scrapers create:
- `results_*.csv` - Spreadsheet format
- `results_*.jsonl` - JSON lines format

Example columns:
```
name, address, latitude, longitude, phone, email, website, 
google_maps_url, category, rating, hours, price_level, 
business_status, scraped_at
```

## 🚀 Quick Start

**Option 1: Keyword Search**
```bash
python scraper.py --keyword "restaurant" --location "Miami"
```

**Option 2: From Link**
```bash
python scraper_by_link.py
# Paste: https://www.google.com/maps/search/cafe+in+NYC/
```

**Option 3: Custom Max**
```bash
python scraper.py --keyword "gym" --location "LA" --max 100
```

## 📧 Email Scraping Details

**Where it looks:**
1. Google Maps listing (visible emails)
2. Business website homepage
3. Contact page (if no email on homepage)

**What it filters out:**
- test@gmail.com, demo@company.com
- sample@, fake@, dummy@
- noreply@, no-reply@
- example.com, test.com
- Image files (.png, .jpg, etc.)

**Real emails found:**
- info@business.com ✅
- contact@company.com ✅
- hello@startup.io ✅

## ⏱️ Performance

| Businesses | Time (Estimated) |
|-----------|------------------|
| 10 | ~5-7 minutes |
| 50 | ~25-35 minutes |
| 100 | ~50-70 minutes |

## 🔧 Advanced Options

**Change max results:**
```bash
--max 100
```

**Use different proxy file:**
```bash
--proxy-file my_proxies.txt
```

**Debug mode (visible browser):**
```bash
--headless false
```

## 📝 Notes

- Both scrapers work identically
- Email scraping is automatic
- Fake emails are filtered out
- Results save incrementally
- Proxies rotate automatically

## 🎉 Ready to Use!

Just run either scraper and start collecting data with emails!
