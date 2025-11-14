#!/usr/bin/env python3
"""
Google Maps Scraper by Link using Playwright
Accepts Google Maps URLs and scrapes place details with proxy rotation and anti-bot detection
"""

import argparse
import asyncio
import csv
import json
import logging
import random
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set
from urllib.parse import quote_plus, urlparse, parse_qs, unquote

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeout
from geopy.distance import geodesic

from config import SELECTORS, TIMING, GEO_TOLERANCE_METERS, USER_AGENTS


# Setup logging
def setup_logging(log_file: str = "scraper_link.log"):
    """Configure logging to file and console"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)


logger = setup_logging()


class ProgressTracker:
    """Track and display scraping progress"""
    def __init__(self, total: int):
        self.total = total
        self.success = 0
        self.failed = 0
        self.current = 0
    
    def increment_success(self):
        self.success += 1
        self.current += 1
        self.display()
    
    def increment_failed(self):
        self.failed += 1
        self.current += 1
        self.display()
    
    def display(self):
        percent = (self.current / self.total * 100) if self.total > 0 else 0
        bar_length = 30
        filled = int(bar_length * self.current / self.total) if self.total > 0 else 0
        bar = '=' * filled + '>' + '.' * (bar_length - filled - 1) if filled < bar_length else '=' * bar_length
        
        print(f"\r[{bar}] {self.current}/{self.total} | Success: {self.success} | Failed: {self.failed} | {percent:.1f}%", end='', flush=True)
        
        if self.current >= self.total:
            print()  # New line when complete


class IncrementalSaver:
    """Save results incrementally as they're scraped"""
    def __init__(self, link_type: str):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.base_filename = f"results_link_{link_type}_{timestamp}"
        self.csv_filename = f"{self.base_filename}.csv"
        self.jsonl_filename = f"{self.base_filename}.jsonl"
        self.resume_filename = f"{self.base_filename}_resume.json"
        self.failed_filename = f"{self.base_filename}_failed.txt"
        self.csv_initialized = False
        self.scraped_urls = set()
        
    def save_place(self, place: Dict):
        """Save a single place immediately"""
        # Save to CSV
        try:
            import os
            file_exists = os.path.exists(self.csv_filename)
            with open(self.csv_filename, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=place.keys())
                if not file_exists:
                    writer.writeheader()
                writer.writerow(place)
        except Exception as e:
            logger.error(f"Error saving to CSV: {e}")
        
        # Save to JSONL
        try:
            with open(self.jsonl_filename, 'a', encoding='utf-8') as f:
                f.write(json.dumps(place) + '\n')
        except Exception as e:
            logger.error(f"Error saving to JSONL: {e}")
        
        # Track scraped URL
        if 'google_maps_url' in place:
            self.scraped_urls.add(place['google_maps_url'])
            self.save_resume_state()
    
    def save_failed_url(self, url: str, error: str):
        """Save failed URLs for manual review"""
        try:
            with open(self.failed_filename, 'a', encoding='utf-8') as f:
                f.write(f"{url} | Error: {error}\n")
        except Exception as e:
            logger.error(f"Error saving failed URL: {e}")
    
    def save_resume_state(self):
        """Save current progress for resume capability"""
        try:
            with open(self.resume_filename, 'w', encoding='utf-8') as f:
                json.dump({
                    'scraped_urls': list(self.scraped_urls),
                    'timestamp': datetime.now().isoformat()
                }, f)
        except Exception as e:
            logger.error(f"Error saving resume state: {e}")
    
    def load_resume_state(self) -> Set[str]:
        """Load previously scraped URLs"""
        import os
        if os.path.exists(self.resume_filename):
            try:
                with open(self.resume_filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return set(data.get('scraped_urls', []))
            except Exception as e:
                logger.error(f"Error loading resume state: {e}")
        return set()


class ProxyManager:
    """Manages proxy rotation from file"""
    
    def __init__(self, proxy_file: Optional[str] = None):
        self.proxies = []
        self.current_index = 0
        
        if proxy_file and Path(proxy_file).exists():
            self.load_proxies(proxy_file)
        else:
            logger.warning(f"No proxy file provided or file not found: {proxy_file}")
    
    def load_proxies(self, proxy_file: str):
        """Load proxies from file (format: ip:port:username:password)"""
        try:
            with open(proxy_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split(':')
                        if len(parts) >= 2:
                            proxy_config = {
                                'server': f"http://{parts[0]}:{parts[1]}"
                            }
                            if len(parts) >= 4:
                                proxy_config['username'] = parts[2]
                                proxy_config['password'] = parts[3]
                            self.proxies.append(proxy_config)
            logger.info(f"Loaded {len(self.proxies)} proxies from {proxy_file}")
        except Exception as e:
            logger.error(f"Error loading proxies: {e}")
    
    def get_next_proxy(self) -> Optional[Dict]:
        """Get next proxy in rotation"""
        if not self.proxies:
            return None
        
        proxy = self.proxies[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.proxies)
        return proxy


class LinkScraper:
    """Main scraper class for Google Maps links"""
    
    def __init__(self, maps_url: str, max_results: int, headless: bool, proxy_manager: ProxyManager, 
                 saver: IncrementalSaver, progress: ProgressTracker, skip_websites: bool = False):
        self.maps_url = maps_url
        self.max_results = max_results
        self.headless = headless
        self.proxy_manager = proxy_manager
        self.saver = saver
        self.progress = progress
        self.skip_websites = skip_websites
        self.scraped_places = []
        self.seen_places = set()
        
        # Email regex pattern
        self.email_pattern = re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        )
        
    async def setup_browser(self, proxy: Optional[Dict] = None) -> Tuple[Browser, BrowserContext, any]:
        """Setup browser with optional proxy"""
        self.playwright = await async_playwright().start()
        
        browser_args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
            '--no-sandbox',
            '--lang=en-US'
        ]
        
        # Launch options
        launch_options = {
            'headless': self.headless,
            'args': browser_args
        }
        
        # Add proxy to launch options if provided
        if proxy:
            launch_options['proxy'] = proxy
            logger.info(f"Using proxy: {proxy['server']}")
        
        browser = await self.playwright.chromium.launch(**launch_options)
        
        context_options = {
            'user_agent': random.choice(USER_AGENTS),
            'viewport': {'width': 1920, 'height': 1080},
            'locale': 'en-US',
            'timezone_id': 'America/New_York',
            'extra_http_headers': {
                'Accept-Language': 'en-US,en;q=0.9'
            }
        }
        
        context = await browser.new_context(**context_options)
        
        # Clear cookies
        await context.clear_cookies()
        
        # Add stealth scripts
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'language', {get: () => 'en-US'});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            window.chrome = {runtime: {}};
        """)
        
        return browser, context, self.playwright
    
    async def random_delay(self, min_sec: float = None, max_sec: float = None):
        """Add random human-like delay"""
        min_sec = min_sec or TIMING['min_delay']
        max_sec = max_sec or TIMING['max_delay']
        await asyncio.sleep(random.uniform(min_sec, max_sec))
    
    async def check_for_captcha(self, page: Page) -> bool:
        """Check if CAPTCHA or blocking is detected"""
        try:
            captcha = await page.query_selector(SELECTORS['captcha_indicator'])
            if captcha:
                logger.warning("CAPTCHA detected!")
                return True
            
            # Check for common blocking messages
            content = await page.content()
            blocking_keywords = ['unusual traffic', 'automated requests', 'verify you', 'not a robot']
            if any(keyword in content.lower() for keyword in blocking_keywords):
                logger.warning("Anti-bot blocking detected!")
                return True
                
        except Exception as e:
            logger.debug(f"Error checking for CAPTCHA: {e}")
        
        return False
    
    def detect_link_type(self, url: str) -> str:
        """Detect the type of Google Maps link"""
        if '/search/' in url or 'search?' in url:
            return 'search'
        elif '/place/' in url:
            return 'place'
        elif 'goo.gl' in url or 'maps.app.goo.gl' in url:
            return 'short'
        else:
            return 'unknown'
    
    async def resolve_short_link(self, page: Page, short_url: str) -> str:
        """Resolve short Google Maps link to full URL"""
        try:
            logger.info(f"Resolving short link: {short_url}")
            await page.goto(short_url, timeout=TIMING['page_load_timeout'], wait_until='domcontentloaded')
            await self.random_delay(2, 3)
            return page.url
        except Exception as e:
            logger.error(f"Error resolving short link: {e}")
            return short_url
    
    async def navigate_to_link(self, page: Page) -> bool:
        """Navigate to the Google Maps link"""
        try:
            url = self.maps_url
            link_type = self.detect_link_type(url)
            
            logger.info(f"Link type detected: {link_type}")
            
            # Resolve short links first
            if link_type == 'short':
                url = await self.resolve_short_link(page, url)
                link_type = self.detect_link_type(url)
                logger.info(f"Resolved to: {url}")
            
            # Ensure English language
            if '?hl=' not in url and '&hl=' not in url:
                separator = '&' if '?' in url else '?'
                url = f"{url}{separator}hl=en"
            
            logger.info(f"Navigating to: {url}")
            await page.goto(url, timeout=TIMING['page_load_timeout'], wait_until='domcontentloaded')
            await self.random_delay(2, 4)
            
            # Check for blocking
            if await self.check_for_captcha(page):
                return False
            
            # Wait for content to load based on link type
            if link_type == 'search':
                try:
                    await page.wait_for_selector(SELECTORS['results_container'], timeout=10000)
                    logger.info("Search results loaded")
                    return True
                except PlaywrightTimeout:
                    logger.error("Results container not found")
                    return False
            elif link_type == 'place':
                try:
                    await page.wait_for_selector(SELECTORS['place_name'], timeout=10000)
                    logger.info("Place page loaded")
                    return True
                except PlaywrightTimeout:
                    logger.error("Place name not found")
                    return False
            else:
                logger.warning(f"Unknown link type, attempting to scrape anyway")
                return True
                
        except Exception as e:
            logger.error(f"Error navigating to link: {e}")
            return False

    
    async def scroll_results(self, page: Page):
        """Scroll through results to load more items until no more results appear"""
        try:
            results_container = await page.query_selector(SELECTORS['results_container'])
            if not results_container:
                return
            
            logger.info("Scrolling to load all results...")
            previous_count = 0
            no_change_count = 0
            max_scrolls = 50
            scroll_count = 0
            
            while scroll_count < max_scrolls:
                await results_container.evaluate("el => el.scrollBy(0, el.scrollHeight)")
                await asyncio.sleep(TIMING['scroll_delay'])
                
                current_results = await page.query_selector_all(SELECTORS['result_items'])
                current_count = len(current_results)
                
                if current_count == previous_count:
                    no_change_count += 1
                    if no_change_count >= 3:
                        logger.info(f"Reached end of results after {scroll_count} scrolls")
                        break
                else:
                    no_change_count = 0
                    logger.debug(f"Loaded {current_count} results so far...")
                
                previous_count = current_count
                scroll_count += 1
            
            if scroll_count >= max_scrolls:
                logger.info(f"Reached maximum scroll limit ({max_scrolls})")
                
        except Exception as e:
            logger.debug(f"Error scrolling: {e}")
    
    async def extract_coordinates(self, page: Page) -> Tuple[Optional[float], Optional[float]]:
        """Extract latitude and longitude from URL or page content"""
        try:
            url = page.url
            if '@' in url:
                coords_part = url.split('@')[1].split(',')
                if len(coords_part) >= 2:
                    lat = float(coords_part[0])
                    lon = float(coords_part[1])
                    logger.debug(f"Coordinates from URL: {lat}, {lon}")
                    return lat, lon
            
            lat_lon = await page.evaluate(r"""() => {
                const metaTag = document.querySelector('meta[itemprop="geo"]');
                if (metaTag) {
                    const content = metaTag.getAttribute('content');
                    if (content) {
                        const parts = content.split(';');
                        if (parts.length >= 2) {
                            return {
                                lat: parseFloat(parts[0].split('=')[1]),
                                lon: parseFloat(parts[1].split('=')[1])
                            };
                        }
                    }
                }
                
                const scripts = document.querySelectorAll('script');
                for (const script of scripts) {
                    const text = script.textContent;
                    if (text && text.includes('center')) {
                        const match = text.match(/center['":\s]+\[([0-9.-]+),\s*([0-9.-]+)\]/);
                        if (match) {
                            return {lat: parseFloat(match[1]), lon: parseFloat(match[2])};
                        }
                    }
                }
                return null;
            }""")
            
            if lat_lon and lat_lon.get('lat') and lat_lon.get('lon'):
                logger.debug(f"Coordinates from page: {lat_lon['lat']}, {lat_lon['lon']}")
                return lat_lon['lat'], lat_lon['lon']
                
        except Exception as e:
            logger.debug(f"Error extracting coordinates: {e}")
        return None, None
    
    async def extract_text(self, page: Page, selector: str) -> Optional[str]:
        """Safely extract text from element"""
        try:
            element = await page.query_selector(selector)
            if element:
                text = await element.inner_text()
                return text.strip()
        except Exception:
            pass
        return None
    
    async def extract_attribute(self, page: Page, selector: str, attribute: str) -> Optional[str]:
        """Safely extract attribute from element"""
        try:
            element = await page.query_selector(selector)
            if element:
                return await element.get_attribute(attribute)
        except Exception:
            pass
        return None
    
    def extract_emails_from_text(self, text: str) -> Set[str]:
        """Extract email addresses from text using regex"""
        if not text:
            return set()
        
        emails = set(self.email_pattern.findall(text))
        
        filtered_emails = set()
        exclude_patterns = [
            'example.com', 'test.com', 'domain.com', 
            'email.com', 'yourdomain.com', 'yoursite.com',
            'sentry.io', 'wixpress.com', 'schema.org',
            '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp',
            'test@', 'demo@', 'sample@', 'noreply@', 'no-reply@',
            'admin@example', 'user@example', 'info@example',
            '@test.', '@demo.', '@sample.', '@placeholder.',
            'placeholder@', 'fake@', 'dummy@'
        ]
        
        for email in emails:
            email_lower = email.lower()
            # Skip if contains any exclude pattern
            if any(pattern in email_lower for pattern in exclude_patterns):
                continue
            # Skip if it's just test/demo email
            if email_lower.startswith(('test', 'demo', 'sample', 'fake', 'dummy')):
                continue
            filtered_emails.add(email)
        
        return filtered_emails
    
    async def scrape_emails_from_google_maps(self, page: Page) -> Set[str]:
        """Extract emails directly from Google Maps listing"""
        emails = set()
        
        try:
            page_text = await page.evaluate("() => document.body.innerText")
            emails.update(self.extract_emails_from_text(page_text))
            
            selectors_to_check = [
                'div[role="main"]',
                'div.m6QErb',
                'button[data-item-id]',
                'a[href^="mailto:"]'
            ]
            
            for selector in selectors_to_check:
                try:
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        text = await element.inner_text()
                        emails.update(self.extract_emails_from_text(text))
                        
                        href = await element.get_attribute('href')
                        if href and 'mailto:' in href:
                            email = href.replace('mailto:', '').split('?')[0]
                            if '@' in email:
                                emails.add(email)
                except Exception:
                    continue
            
            if emails:
                logger.info(f"Found {len(emails)} email(s) on Google Maps: {', '.join(emails)}")
                
        except Exception as e:
            logger.debug(f"Error scraping emails from Google Maps: {e}")
        
        return emails
    
    async def scrape_emails_from_website(self, website_url: str, context: BrowserContext) -> Set[str]:
        """Visit business website and scrape for emails - FAST + THOROUGH"""
        emails = set()
        
        if not website_url or 'google.com' in website_url:
            return emails
        
        page = None
        try:
            logger.debug(f"Checking: {website_url}")
            page = await context.new_page()
            
            # SPEED: Block images, CSS, fonts - only load text
            await page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "stylesheet", "font", "media"] else route.continue_())
            
            # Check homepage - fast timeout
            await page.goto(website_url, timeout=5000, wait_until='domcontentloaded')
            
            # Get all text content
            page_text = await page.evaluate("() => document.body.innerText")
            page_html = await page.content()
            
            emails.update(self.extract_emails_from_text(page_text))
            emails.update(self.extract_emails_from_text(page_html))
            
            # SMART: Only check contact if NO emails found on homepage
            if not emails:
                try:
                    # Quick check for contact link
                    contact_link = await page.query_selector('a[href*="contact"]')
                    if contact_link:
                        href = await contact_link.get_attribute('href')
                        if href and not href.startswith('mailto:'):
                            if href.startswith('/'):
                                from urllib.parse import urljoin
                                href = urljoin(website_url, href)
                            
                            if href.startswith('http'):
                                # Fast contact page check
                                await page.goto(href, timeout=4000, wait_until='domcontentloaded')
                                contact_text = await page.evaluate("() => document.body.innerText")
                                emails.update(self.extract_emails_from_text(contact_text))
                except Exception:
                    pass  # Skip if contact page fails
            
            if emails:
                logger.info(f"✓ {len(emails)} email(s): {', '.join(emails)}")
            else:
                logger.debug("✗ No emails")
                
        except Exception as e:
            logger.debug(f"Skip: {e}")
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
        
        return emails

    
    async def parse_place_details(self, page: Page, context: BrowserContext) -> Optional[Dict]:
        """Parse all details from a place page"""
        try:
            await self.random_delay(TIMING['item_parse_delay'], TIMING['item_parse_delay'] + 0.5)
            
            # Don't wait for networkidle - it's too slow. Just wait for domcontentloaded
            try:
                await page.wait_for_load_state('domcontentloaded', timeout=5000)
            except:
                pass  # Continue anyway
            
            if await self.check_for_captcha(page):
                raise Exception("CAPTCHA detected during parsing")
            
            place_url = page.url
            
            name = await self.extract_text(page, SELECTORS['place_name'])
            if not name:
                logger.debug("Could not extract place name, skipping")
                return None
            
            lat, lon = await self.extract_coordinates(page)
            
            if self.is_duplicate(name, lat, lon):
                logger.debug(f"Duplicate found: {name}")
                return None
            
            address = await self.extract_text(page, SELECTORS['place_address'])
            phone = await self.extract_text(page, SELECTORS['place_phone'])
            
            emails_from_maps = await self.scrape_emails_from_google_maps(page)
            
            website = await self.extract_attribute(page, SELECTORS['place_website'], 'href')
            
            if not website:
                try:
                    website = await page.evaluate("""() => {
                        let menuButtons = document.querySelectorAll('button[aria-label*="Menu"], button[data-item-id*="menu"]');
                        for (let btn of menuButtons) {
                            btn.click();
                        }
                        
                        return new Promise(resolve => {
                            setTimeout(() => {
                                let links = document.querySelectorAll('a[href*="http"]');
                                for (let link of links) {
                                    let href = link.href;
                                    if (href && !href.includes('google.com') && !href.includes('gstatic.com')) {
                                        resolve(href);
                                        return;
                                    }
                                }
                                resolve(null);
                            }, 1000);
                        });
                    }""")
                    logger.debug(f"Website from Menu tab: {website}")
                except Exception as e:
                    logger.debug(f"Error checking Menu tab for website: {e}")
            
            emails_from_website = set()
            if website and not self.skip_websites:
                emails_from_website = await self.scrape_emails_from_website(website, context)
            
            all_emails = emails_from_maps.union(emails_from_website)
            email_string = ', '.join(sorted(all_emails)) if all_emails else None
            
            category = await self.extract_text(page, SELECTORS['place_category'])
            
            rating = None
            try:
                rating = await page.evaluate(r"""() => {
                    let selectors = [
                        'div.F7nice span[aria-hidden="true"]',
                        'span.ceNzKf',
                        'div.fontDisplayLarge',
                        'span[role="img"][aria-label*="star"]'
                    ];
                    
                    for (let selector of selectors) {
                        let elem = document.querySelector(selector);
                        if (elem) {
                            let text = elem.textContent || elem.getAttribute('aria-label') || '';
                            let match = text.match(/(\d+\.?\d*)/);
                            if (match) {
                                let num = parseFloat(match[1]);
                                if (num >= 0 && num <= 5) {
                                    return num;
                                }
                            }
                        }
                    }
                    
                    let allText = document.body.innerText;
                    let ratingMatch = allText.match(/(\d+\.\d+)\s*stars?/i);
                    if (ratingMatch) {
                        return parseFloat(ratingMatch[1]);
                    }
                    
                    return null;
                }""")
                    
                logger.debug(f"Rating extracted: {rating}")
            except Exception as e:
                logger.debug(f"Error extracting rating: {e}")
            
            hours = None
            try:
                hours = await page.evaluate("""() => {
                    let hoursButton = document.querySelector('button[data-item-id*="oh"], button[aria-label*="Hours"]');
                    if (hoursButton) {
                        let text = hoursButton.getAttribute('aria-label') || hoursButton.textContent;
                        if (text) return text.trim();
                    }
                    
                    let hoursDiv = document.querySelector('div[aria-label*="Hours"], div.t39EBf');
                    if (hoursDiv) {
                        return hoursDiv.textContent.trim();
                    }
                    
                    let statusSpans = document.querySelectorAll('span.ZDu9vd, span.o0Svhf');
                    for (let span of statusSpans) {
                        let text = span.textContent.trim();
                        if (text.match(/open|closed|opens|closes/i)) {
                            return text;
                        }
                    }
                    
                    return null;
                }""")
                
                logger.debug(f"Hours extracted: {hours}")
            except Exception as e:
                logger.debug(f"Error extracting hours: {e}")
            
            price = None
            try:
                price = await self.extract_attribute(page, SELECTORS['place_price'], 'aria-label')
                
                if not price:
                    price = await page.evaluate("""() => {
                        const priceSpans = document.querySelectorAll('span[aria-label*="Price"], span[aria-label*="price"]');
                        for (const span of priceSpans) {
                            const label = span.getAttribute('aria-label');
                            if (label && (label.includes('Price') || label.includes('price'))) {
                                return label;
                            }
                        }
                        
                        const dollarSigns = document.querySelector('span.mgr77e');
                        if (dollarSigns) {
                            return dollarSigns.textContent.trim();
                        }
                        return null;
                    }""")
                    
                logger.debug(f"Price level extracted: {price}")
            except Exception as e:
                logger.debug(f"Error extracting price: {e}")
            
            status = await self.extract_text(page, SELECTORS['place_status'])
            
            place_data = {
                'name': name,
                'address': address,
                'latitude': lat,
                'longitude': lon,
                'phone': phone,
                'email': email_string,
                'website': website,
                'google_maps_url': place_url,
                'category': category,
                'rating': rating,
                'hours': hours,
                'price_level': price,
                'business_status': status,
                'scraped_at': datetime.now().isoformat()
            }
            
            logger.info(f"Scraped: {name} | Emails: {email_string or 'None found'}")
            return place_data
            
        except Exception as e:
            logger.error(f"Error parsing place details: {e}")
            return None
    
    def is_duplicate(self, name: str, lat: Optional[float], lon: Optional[float]) -> bool:
        """Check if place is duplicate based on name and coordinates"""
        if not name:
            return True
        
        if name in self.seen_places:
            return True
        
        if lat and lon:
            for place in self.scraped_places:
                if place['name'] == name:
                    return True
                
                if place['latitude'] and place['longitude']:
                    distance = geodesic(
                        (lat, lon),
                        (place['latitude'], place['longitude'])
                    ).meters
                    
                    if distance < GEO_TOLERANCE_METERS:
                        return True
        
        self.seen_places.add(name)
        return False
    
    async def collect_results(self, page: Page) -> List[str]:
        """Collect all result links from search page"""
        try:
            await self.scroll_results(page)
            
            result_elements = await page.query_selector_all(SELECTORS['result_items'])
            links = []
            
            for element in result_elements:
                try:
                    href = await element.get_attribute('href')
                    if href and '/maps/place/' in href:
                        links.append(href)
                except Exception:
                    continue
            
            logger.info(f"Found {len(links)} result links (will process up to {self.max_results})")
            return links
            
        except Exception as e:
            logger.error(f"Error collecting results: {e}")
            return []
    
    async def scrape_with_retry(self, max_retries: int = 3) -> List[Dict]:
        """Main scraping method with proxy rotation on failure and incremental saving"""
        retry_count = 0
        
        # Load previously scraped URLs for resume capability
        already_scraped = self.saver.load_resume_state()
        if already_scraped:
            logger.info(f"[RESUME] Found {len(already_scraped)} previously scraped places, will skip them")
        
        while retry_count < max_retries:
            browser = None
            context = None
            playwright = None
            
            try:
                proxy = self.proxy_manager.get_next_proxy()
                
                browser, context, playwright = await self.setup_browser(proxy)
                page = await context.new_page()
                
                if not await self.navigate_to_link(page):
                    raise Exception("Navigation failed or blocked")
                
                link_type = self.detect_link_type(page.url)
                
                if link_type == 'place':
                    # Single place - scrape it directly
                    logger.info("Single place detected, scraping...")
                    
                    # Check if already scraped
                    if page.url in already_scraped:
                        logger.info("[RESUME] Place already scraped, skipping")
                        return self.scraped_places
                    
                    place_data = await self.parse_place_details(page, context)
                    if place_data:
                        # Save immediately
                        self.saver.save_place(place_data)
                        self.scraped_places.append(place_data)
                        self.progress.increment_success()
                    
                elif link_type == 'search':
                    # Search results - collect and scrape all
                    result_links = await self.collect_results(page)
                    
                    if not result_links:
                        raise Exception("No results found")
                    
                    # Filter out already scraped links
                    result_links = [link for link in result_links if link not in already_scraped]
                    logger.info(f"[RESUME] {len(result_links)} new places to scrape")
                    
                    for i, link in enumerate(result_links):
                        if len(self.scraped_places) >= self.max_results:
                            logger.info(f"Reached max results limit: {self.max_results}")
                            break
                        
                        # Retry logic for individual place
                        place_retry = 0
                        max_place_retry = 2
                        place_data = None
                        
                        while place_retry < max_place_retry and not place_data:
                            try:
                                await page.goto(link, timeout=TIMING['navigation_timeout'], wait_until='domcontentloaded')
                                await self.random_delay(2, 3)
                                
                                if await self.check_for_captcha(page):
                                    raise Exception("CAPTCHA detected, rotating proxy")
                                
                                place_data = await self.parse_place_details(page, context)
                                
                                if place_data:
                                    # Save immediately
                                    self.saver.save_place(place_data)
                                    self.scraped_places.append(place_data)
                                    self.progress.increment_success()
                                else:
                                    raise Exception("Failed to parse place data")
                                
                                # Go back to results
                                await page.go_back(timeout=TIMING['navigation_timeout'])
                                await self.random_delay(0.5, 1)
                                
                            except Exception as e:
                                place_retry += 1
                                error_msg = str(e)
                                
                                if place_retry >= max_place_retry:
                                    logger.warning(f"[FAILED] Failed to scrape place after {max_place_retry} retries: {error_msg}")
                                    self.saver.save_failed_url(link, error_msg)
                                    self.progress.increment_failed()
                                    break
                                
                                if "CAPTCHA" in error_msg or "blocked" in error_msg.lower():
                                    raise  # Re-raise to trigger full retry
                
                logger.info(f"Successfully scraped {len(self.scraped_places)} places")
                return self.scraped_places
                
            except Exception as e:
                retry_count += 1
                logger.error(f"Attempt {retry_count} failed: {e}")
                
                if retry_count < max_retries:
                    logger.info(f"Rotating proxy and retrying... ({retry_count}/{max_retries})")
                    await asyncio.sleep(2)
                else:
                    logger.error("Max retries reached, giving up")
                
            finally:
                try:
                    if context:
                        await context.close()
                    if browser:
                        await browser.close()
                    if playwright:
                        await playwright.stop()
                except Exception as e:
                    logger.debug(f"Cleanup error (ignored): {e}")
        
        return self.scraped_places


# Note: save_results() is no longer needed - IncrementalSaver handles all saving


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Google Maps Scraper by Link using Playwright',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  python scraper_by_link.py
  
  # Command-line mode with search link
  python scraper_by_link.py --url "https://www.google.com/maps/search/cafe+in+Miami/"
  
  # With single place link
  python scraper_by_link.py --url "https://www.google.com/maps/place/Starbucks/@40.7,-74.0,17z"
  
  # With short link
  python scraper_by_link.py --url "https://maps.app.goo.gl/abc123"
        """
    )
    
    parser.add_argument('--url', help='Google Maps URL (search, place, or short link)')
    parser.add_argument('--max', type=int, default=70, help='Maximum number of places to scrape (default: 70)')
    parser.add_argument('--headless', type=str, default='true', choices=['true', 'false'], 
                       help='Run in headless mode (default: true)')
    parser.add_argument('--proxy-file', type=str, default='proxies.txt', help='Path to proxy file')
    parser.add_argument('--scrape-websites', action='store_true', help='Visit websites for emails (slower but finds more emails)')
    
    args = parser.parse_args()
    
    # Interactive mode - always ask for URL
    if not args.url:
        print("\n" + "="*60)
        print("Google Maps Scraper by Link")
        print("="*60)
        print("\nPaste any Google Maps link:")
        print("  - Search results: https://www.google.com/maps/search/cafe+in+Miami/")
        print("  - Single place: https://www.google.com/maps/place/Starbucks/...")
        print("  - Short link: https://maps.app.goo.gl/abc123")
        print()
        maps_url = input("Google Maps URL: ").strip()
        if not maps_url:
            print("[ERROR] URL cannot be empty!")
            return
    else:
        maps_url = args.url
    
    # Validate URL
    if 'google.com/maps' not in maps_url and 'goo.gl' not in maps_url:
        print("[ERROR] Invalid Google Maps URL!")
        return
    
    # Visible browser by default, use args.max, scrape websites for emails
    headless = False  # Show browser so you can watch
    max_results = args.max  # Use the --max argument
    skip_websites = False  # Always scrape websites for emails
    
    logger.info("="*60)
    logger.info("Google Maps Scraper by Link Started")
    logger.info(f"URL: {maps_url}")
    logger.info(f"Max Results: {max_results}")
    logger.info(f"Headless: {headless}")
    logger.info(f"Skip Websites: {skip_websites}")
    logger.info(f"Proxy File: {args.proxy_file or 'None'}")
    logger.info("="*60)
    
    # Initialize components
    proxy_manager = ProxyManager(args.proxy_file)
    
    # Detect link type early for saver
    temp_scraper = LinkScraper.__new__(LinkScraper)
    link_type = temp_scraper.detect_link_type(maps_url)
    
    saver = IncrementalSaver(link_type)
    progress = ProgressTracker(max_results)
    
    if proxy_manager.proxies:
        logger.info(f"[SUCCESS] Loaded {len(proxy_manager.proxies)} proxies - Rotation enabled!")
    else:
        logger.warning("[WARNING] No proxies loaded - Running without proxy rotation")
    
    scraper = LinkScraper(
        maps_url=maps_url,
        max_results=max_results,
        headless=headless,
        proxy_manager=proxy_manager,
        saver=saver,
        progress=progress,
        skip_websites=skip_websites
    )
    
    # Display progress header
    print("\n" + "="*60)
    print("SCRAPING PROGRESS")
    print("="*60)
    
    # Run scraper (results are saved incrementally)
    results = await scraper.scrape_with_retry(max_retries=3)
    
    # Final summary
    print("\n" + "="*60)
    logger.info(f"Scraping completed!")
    logger.info(f"Total successful: {progress.success}")
    logger.info(f"Total failed: {progress.failed}")
    logger.info(f"Results saved to: {saver.csv_filename}")
    logger.info(f"Results saved to: {saver.jsonl_filename}")
    if progress.failed > 0:
        logger.info(f"Failed URLs saved to: {saver.failed_filename}")
    logger.info("="*60)


if __name__ == "__main__":
    asyncio.run(main())
