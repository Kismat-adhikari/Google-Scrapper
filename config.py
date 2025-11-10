"""Configuration file for selectors and settings"""

# Google Maps Selectors
SELECTORS = {
    "search_box": "input#searchboxinput",
    "search_button": "button#searchbox-searchbutton",
    "results_container": "div[role='feed']",
    "result_items": "div[role='feed'] > div > div > a",
    "place_name": "h1.DUwDvf, h1.fontHeadlineLarge",
    "place_address": "button[data-item-id='address'], button[data-tooltip='Copy address']",
    "place_phone": "button[data-item-id*='phone'], button[aria-label*='Phone']",
    "place_website": "a[data-item-id='authority'], a[aria-label*='Website']",
    "place_category": "button[jsaction*='category'], button.DkEaL",
    "place_rating": "div.F7nice > span[role='img'], span.ceNzKf, div.F7nice span[aria-hidden='true']",
    "place_hours": "button[data-item-id*='oh'], div[aria-label*='Hours']",
    "place_price": "span[aria-label*='Price'], span.mgr77e",
    "place_status": "span[class*='ZDu9vd'], span.o0Svhf",
    "captcha_indicator": "iframe[src*='recaptcha'], div[id*='captcha']"
}

# Timing settings (in seconds)
TIMING = {
    "page_load_timeout": 30000,
    "navigation_timeout": 30000,
    "min_delay": 1.5,
    "max_delay": 3.5,
    "scroll_delay": 0.8,
    "item_parse_delay": 0.5
}

# Geolocation tolerance for deduplication (meters)
GEO_TOLERANCE_METERS = 25

# User agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]
