# Email Scraping Feature

## Overview
The scraper now automatically extracts email addresses from both Google Maps listings and business websites.

## How It Works

### 1. Google Maps Email Extraction
- Scans the entire Google Maps listing page for email addresses
- Checks specific sections (info panels, action buttons)
- Detects `mailto:` links
- Uses regex pattern to find emails in page text

### 2. Website Email Extraction
- Visits the business website (if available)
- Scans homepage content for emails
- Automatically checks contact/about pages
- Extracts emails from both visible text and HTML source

### 3. Email Filtering
Filters out common false positives:
- example.com, test.com, domain.com
- Image file extensions (.png, .jpg, etc.)
- Third-party service domains (sentry.io, wixpress.com, etc.)

## Output Format

The email column in CSV/JSONL contains:
- Single email: `info@business.com`
- Multiple emails: `info@business.com, contact@business.com`
- No email found: Empty field

## Example Output

```csv
name,email,website
Victory Sweet Shop,info@victorysweetshop.com,https://victorysweetshop.com/
Stumptown Coffee,,https://www.stumptowncoffee.com/
```

## Technical Details

### New Functions Added:
- `extract_emails_from_text()` - Regex-based email extraction
- `scrape_emails_from_google_maps()` - Extracts emails from Maps listing
- `scrape_emails_from_website()` - Visits and scrapes business website

### Regex Pattern:
```python
r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
```

### Performance Impact:
- Adds 1-3 seconds per business (for website visit)
- Timeout set to 15 seconds for website loading
- Checks up to 3 contact-related pages per website

## Usage

No changes needed - email scraping is automatic:

```bash
python scraper.py --keyword "restaurant" --location "Los Angeles" --max 10
```

The output CSV will now include an `email` column with any found email addresses.
