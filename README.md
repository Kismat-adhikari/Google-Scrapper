# Google Maps Scraper with Playwright

A robust, production-ready Python scraper for Google Maps that uses Playwright with proxy rotation, anti-bot detection, and human-like behavior.

## Features

- **CLI-based**: Run entirely from terminal with command-line arguments
- **Proxy Rotation**: Automatic proxy rotation from file to distribute traffic
- **Anti-Bot Detection**: Detects CAPTCHAs and blocking, automatically rotates proxies
- **Human-like Behavior**: Random delays, scrolling, realistic interactions
- **Deduplication**: Smart deduplication by name and geolocation (25m tolerance)
- **Multiple Output Formats**: Saves results as CSV and JSONL
- **Comprehensive Logging**: Detailed logs to file and console
- **Modular Design**: Easy to customize selectors and settings
- **Headful/Headless Modes**: Debug with visible browser or run headless

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Install Playwright browsers:
```bash
playwright install chromium
```

## Usage

### Basic Examples

**Scrape up to 150 results (default):**
```bash
python scraper.py --keyword "cafe" --location "New York" --headless true
```

**Limit to specific number:**
```bash
python scraper.py --keyword "gym" --location "90210" --max 20 --headless true
```

**Scrape maximum results (200):**
```bash
python scraper.py --keyword "restaurant" --location "Los Angeles" --max 200 --headless true --proxy-file proxies.txt
```

**Headful mode for debugging:**
```bash
python scraper.py --keyword "hotel" --location "Miami" --max 10 --headless false
```

### Command-Line Arguments

- `--keyword` (required): Search term (e.g., "cafe", "gym", "restaurant")
- `--location` (required): City name or zip code (e.g., "New York", "90210")
- `--max` (optional): Maximum number of places to scrape (default: 150, Google Maps typically shows 120-200 max)
- `--headless` (optional): Run in headless mode - "true" or "false" (default: false)
- `--proxy-file` (optional): Path to proxy file (recommended for scrapes over 50 results)

### Proxy File Format

Create a `proxies.txt` file with one proxy per line in this format:
```
ip:port:username:password
```

Example:
```
123.45.67.89:8080:user1:pass1
98.76.54.32:3128:user2:pass2
```

For proxies without authentication:
```
123.45.67.89:8080
98.76.54.32:3128
```

## Scraped Data

The scraper collects the following information for each place:

- Name
- Full address
- Latitude & longitude
- Phone number
- **Email address(es)** - scraped from both Google Maps listing and business website
- Website URL
- Category/type
- Rating (stars)
- Opening hours
- Price level
- Business status
- Timestamp

## Output Files

Results are saved with timestamps in two formats:

- **CSV**: `results_{keyword}_{location}_{timestamp}.csv`
- **JSONL**: `results_{keyword}_{location}_{timestamp}.jsonl`

Example:
```
results_cafe_New_York_20251110_143022.csv
results_cafe_New_York_20251110_143022.jsonl
```

## Configuration

Customize selectors and settings in `config.py`:

- **SELECTORS**: CSS/XPath selectors for Google Maps elements
- **TIMING**: Delays and timeouts for human-like behavior
- **GEO_TOLERANCE_METERS**: Distance tolerance for deduplication (default: 25m)
- **USER_AGENTS**: User agent strings for rotation

## How It Works

1. **Browser Setup**: Launches Chrome with anti-detection measures
2. **Proxy Rotation**: Selects next proxy from rotation pool
3. **Search**: Navigates to Google Maps and searches for keyword + location
4. **Result Collection**: Scrolls and collects all result links
5. **Detail Extraction**: Visits each place and extracts all details
6. **Email Scraping**: 
   - Extracts emails from Google Maps listing
   - Visits business website and scrapes for emails
   - Checks contact/about pages for additional emails
7. **Anti-Bot Handling**: Detects CAPTCHAs/blocking and rotates proxy automatically
8. **Deduplication**: Filters duplicates by name and coordinates
9. **Save Results**: Exports to CSV and JSONL with logging

## Anti-Bot Features

- Randomized user agents
- Human-like delays (1.5-3.5 seconds)
- Realistic scrolling behavior
- Stealth mode (hides webdriver detection)
- Automatic CAPTCHA detection
- Proxy rotation on blocking
- Retry mechanism with exponential backoff

## Logging

All activity is logged to:
- Console (stdout)
- `scraper.log` file

Log levels include progress updates, errors, and debugging information.

## Troubleshooting

**No results found:**
- Try running in headful mode to see what's happening
- Check if Google Maps layout has changed (update selectors in config.py)
- Verify your search terms are valid

**CAPTCHA/Blocking:**
- Use proxy rotation with `--proxy-file`
- Increase delays in config.py
- Run in headless mode to appear less suspicious

**Playwright errors:**
- Ensure browsers are installed: `playwright install chromium`
- Check Python version (3.8+ required)

## Project Structure

```
.
├── scraper.py          # Main scraper script
├── config.py           # Configuration and selectors
├── requirements.txt    # Python dependencies
├── proxies.txt         # Proxy list (user-provided)
├── README.md          # This file
└── scraper.log        # Log file (generated)
```

## License

MIT License - feel free to modify and use for your projects.

## Disclaimer

This scraper is for educational purposes. Always respect website terms of service and robots.txt. Use responsibly and ethically.
