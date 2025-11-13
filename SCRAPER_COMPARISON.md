# Scraper Comparison Guide

You now have **two scrapers** - here's when to use each:

## 📋 Quick Comparison

| Feature | `scraper.py` | `scraper_by_link.py` |
|---------|--------------|---------------------|
| **Input Method** | Keyword + Location | Google Maps URL |
| **Best For** | Building searches | Using existing links |
| **Example Input** | "cafe" + "Miami" | https://maps.google.com/... |
| **Coordinates Required** | No | No |
| **Email Scraping** | ✅ Yes | ✅ Yes |
| **Website Scraping** | ✅ Yes | ✅ Yes |
| **Proxy Support** | ✅ Yes | ✅ Yes |
| **Default Max** | 150 results | 150 results |
| **Output Format** | CSV + JSONL | CSV + JSONL |

---

## 🎯 When to Use `scraper.py` (Main Scraper)

**Use this when you want to:**
- Search by business type and location
- Build searches from scratch
- Scrape multiple cities or keywords
- Have full control over search terms

**Examples:**
```bash
# Interactive mode
python scraper.py
# Then enter: keyword="gym", location="Miami"

# Command-line mode
python scraper.py --keyword "restaurant" --location "New York"
python scraper.py --keyword "cafe" --location "90210" --max 50
```

**Perfect for:**
- Lead generation campaigns
- Market research by category
- Competitor analysis
- Building business directories

---

## 🔗 When to Use `scraper_by_link.py` (Link Scraper)

**Use this when you have:**
- An existing Google Maps search link
- A shared place/business link
- Bookmarked searches
- Short/redirect links (goo.gl)

**Examples:**
```bash
# Interactive mode
python scraper_by_link.py
# Then paste any Google Maps URL

# Command-line mode
python scraper_by_link.py --url "https://www.google.com/maps/search/gym+in+Miami/"
python scraper_by_link.py --url "https://maps.app.goo.gl/abc123"
```

**Perfect for:**
- Re-scraping saved searches
- Working with client-provided links
- Scraping specific filtered searches
- Quick one-off scrapes

---

## 💡 Pro Tips

### Both Scrapers Support:

1. **Email Scraping** - Automatically finds emails from:
   - Google Maps listings
   - Business websites
   - Contact pages

2. **Proxy Rotation** - Use for large scrapes:
   ```bash
   --proxy-file proxies.txt
   ```

3. **Headless Mode** - Faster and more stable (default):
   ```bash
   --headless true
   ```

4. **Custom Limits** - Control how many results:
   ```bash
   --max 50    # Scrape up to 50 results
   --max 200   # Scrape up to 200 results
   ```

### Recommended Workflow:

**For systematic scraping:**
```bash
# Use main scraper for multiple searches
python scraper.py --keyword "gym" --location "Miami" --max 150
python scraper.py --keyword "gym" --location "Orlando" --max 150
python scraper.py --keyword "gym" --location "Tampa" --max 150
```

**For ad-hoc scraping:**
```bash
# Use link scraper for quick jobs
python scraper_by_link.py --url "PASTE_LINK_HERE"
```

---

## 📊 Output Files

Both scrapers create the same output format:

**Main Scraper:**
- `results_gym_Miami_20251112_185414.csv`
- `results_gym_Miami_20251112_185414.jsonl`

**Link Scraper:**
- `results_link_search_20251112_185414.csv`
- `results_link_search_20251112_185414.jsonl`

**Data Fields (Both):**
- name, address, latitude, longitude
- phone, **email**, website
- category, rating, hours, price_level
- business_status, scraped_at

---

## 🚀 Quick Start Examples

### Scenario 1: "I want to scrape all gyms in Miami"
```bash
python scraper.py --keyword "gym" --location "Miami" --headless true
```

### Scenario 2: "Someone sent me this Google Maps link"
```bash
python scraper_by_link.py --url "https://www.google.com/maps/search/..."
```

### Scenario 3: "I need 200 restaurants in NYC with emails"
```bash
python scraper.py --keyword "restaurant" --location "New York" --max 200 --proxy-file proxies.txt
```

### Scenario 4: "I have a bookmarked search I want to re-scrape"
```bash
python scraper_by_link.py --url "YOUR_BOOKMARKED_LINK"
```

---

## ⚙️ Configuration

Both scrapers share the same:
- `config.py` - Selectors and timing settings
- `proxies.txt` - Proxy list
- `requirements.txt` - Dependencies

No need to configure anything separately!

---

## 🎓 Summary

**Choose based on your input:**
- Have keyword + location? → Use `scraper.py`
- Have Google Maps link? → Use `scraper_by_link.py`

**Both scrapers:**
- Find emails automatically
- Support proxies
- Output same format
- Work without coordinates
- Default to 150 results

**Can't decide?** Start with `scraper.py` for most use cases!
