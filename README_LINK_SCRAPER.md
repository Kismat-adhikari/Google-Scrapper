# Google Maps Scraper by Link

A specialized version of the Google Maps scraper that accepts **any Google Maps URL** instead of keyword + location.

## Key Features

- **Accepts any Google Maps link** - no coordinates required
- **Auto-detects link type** (search results, single place, or short link)
- **Same scraping power** - emails, phone, website, ratings, hours, etc.
- **Proxy rotation** and anti-bot detection
- **150 results default** - scrapes up to 150 places from search links

## Supported Link Types

### 1. Search Result Links
```
https://www.google.com/maps/search/cafe+in+Miami/
https://www.google.com/maps/search/gym+near+me/
```
→ Scrapes all results from the search (up to max limit)

### 2. Single Place Links
```
https://www.google.com/maps/place/Starbucks/@40.7,-74.0,17z/
https://www.google.com/maps/place/Miami+Strong+Gym/
```
→ Scrapes just that one place

### 3. Short/Redirect Links
```
https://maps.app.goo.gl/abc123
https://goo.gl/maps/xyz789
```
→ Automatically resolves and scrapes

**Note:** Links do NOT need coordinates (@lat,long) - the scraper works with any valid Google Maps URL!

## Installation

Same as the main scraper:
```bash
pip install -r requirements.txt
playwright install chromium
```

## Usage

### Interactive Mode (Easiest)

Just run the script and paste your link:
```bash
python scraper_by_link.py
```

Then paste any Google Maps URL when prompted.

### Command-Line Mode

**Scrape search results:**
```bash
python scraper_by_link.py --url "https://www.google.com/maps/search/restaurant+in+NYC/"
```

**Scrape single place:**
```bash
python scraper_by_link.py --url "https://www.google.com/maps/place/Starbucks/@40.7,-74.0,17z/"
```

**With custom max and proxies:**
```bash
python scraper_by_link.py --url "https://www.google.com/maps/search/gym+in+Miami/" --max 50 --proxy-file proxies.txt
```

**Headful mode for debugging:**
```bash
python scraper_by_link.py --url "YOUR_LINK" --headless false
```

## Command-Line Arguments

- `--url` (optional): Google Maps URL - if not provided, will prompt interactively
- `--max` (optional): Maximum number of places to scrape (default: 150)
- `--headless` (optional): Run in headless mode - "true" or "false" (default: true)
- `--proxy-file` (optional): Path to proxy file (default: proxies.txt)

## Output

Results are saved with timestamps:
- **CSV**: `results_link_search_20251112_185414.csv`
- **JSONL**: `results_link_search_20251112_185414.jsonl`

Same data fields as the main scraper:
- Name, address, coordinates
- Phone, **email(s)**, website
- Category, rating, hours, price level
- Business status, timestamp

## How It Works

1. **Paste any Google Maps link** (search, place, or short link)
2. **Auto-detects link type** and resolves short links
3. **Scrapes accordingly**:
   - Search links → scrolls and collects all results
   - Place links → scrapes that single place
4. **Extracts emails** from both Google Maps and business websites
5. **Saves results** to CSV and JSONL

## Examples

### Example 1: Search Link
```bash
python scraper_by_link.py --url "https://www.google.com/maps/search/cafe+in+Miami/"
```
→ Found 121 results, scraped up to 150 (or your --max)

### Example 2: Single Place
```bash
python scraper_by_link.py --url "https://www.google.com/maps/place/Miami+Strong+Gym/"
```
→ Scraped 1 place with all details including emails

### Example 3: Short Link
```bash
python scraper_by_link.py --url "https://maps.app.goo.gl/abc123"
```
→ Resolves link first, then scrapes

## Differences from Main Scraper

| Feature | Main Scraper | Link Scraper |
|---------|-------------|--------------|
| Input | Keyword + Location | Any Google Maps URL |
| Use Case | Build searches from scratch | Scrape existing links |
| Coordinates Required | No | No |
| Email Scraping | ✅ Yes | ✅ Yes |
| Proxy Support | ✅ Yes | ✅ Yes |
| Output Format | Same | Same |

## When to Use Which?

**Use `scraper.py` (main) when:**
- You want to search by keyword + location
- Building searches from scratch
- Need to scrape multiple cities/keywords

**Use `scraper_by_link.py` when:**
- You already have a Google Maps link
- Someone shared a search/place link with you
- Working with bookmarked searches
- Need to re-scrape a specific search

## Tips

1. **For large scrapes** (50+ results), use `--proxy-file proxies.txt`
2. **Test first** with `--max 5` to verify the link works
3. **Short links** work but add ~2-3 seconds for resolution
4. **Search links** without coordinates work perfectly fine
5. **Headless mode** (default) is faster and more stable

## Troubleshooting

**"Invalid Google Maps URL" error:**
- Make sure the URL contains `google.com/maps` or `goo.gl`
- Try copying the link again from your browser

**No results found:**
- Check if the link works in your browser first
- Try with `--headless false` to see what's happening
- The search might have no results in that location

**CAPTCHA/Blocking:**
- Use `--proxy-file proxies.txt` for proxy rotation
- Reduce `--max` to scrape fewer results
- Add delays between runs

## License

MIT License - same as the main scraper.
