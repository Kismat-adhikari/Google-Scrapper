#!/usr/bin/env python3
"""
Google Maps Scraper using Playwright
Scrapes place details with proxy rotation and anti-bot detection
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
from urllib.parse import quote_plus

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeout
from geopy.distance import geodesic

from config import SELECTORS, TIMING, GEO_TOLERANCE_METERS, USER_AGENTS


# Setup logging
def setup_logging(log_file: str = "scraper.log"):
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


class PlaceScraper:
    """Main scraper class for Google Maps"""
    
    def __init__(self, keyword: str, location: str, max_results: int, 
                 headless: bool, proxy_manager: ProxyManager):
        self.keyword = keyword
        self.location = location
        self.max_results = max_results
        self.headless = headless
        self.proxy_manager = proxy_manager
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
    
    async def search_google_maps(self, page: Page) -> bool:
        """Navigate to Google Maps and perform search"""
        try:
            # First visit Google Maps in English to set language
            logger.info("Opening Google Maps in English...")
            await page.goto('https://www.google.com/maps?hl=en', timeout=TIMING['page_load_timeout'], wait_until='domcontentloaded')
            await self.random_delay(1, 2)
            
            # Now perform the search
            search_query = f"{self.keyword} in {self.location}"
            url = f"https://www.google.com/maps/search/{quote_plus(search_query)}?hl=en"
            
            logger.info(f"Navigating to: {url}")
            await page.goto(url, timeout=TIMING['page_load_timeout'], wait_until='domcontentloaded')
            await self.random_delay(2, 4)
            
            # Check for blocking
            if await self.check_for_captcha(page):
                return False
            
            # Wait for results to load
            try:
                await page.wait_for_selector(SELECTORS['results_container'], timeout=10000)
                logger.info("Search results loaded")
                return True
            except PlaywrightTimeout:
                logger.error("Results container not found")
                return False
                
        except Exception as e:
            logger.error(f"Error during search: {e}")
            return False
    
    async def scroll_results(self, page: Page):
        """Scroll through results to load more items"""
        try:
            results_container = await page.query_selector(SELECTORS['results_container'])
            if not results_container:
                return
            
            logger.info("Scrolling to load more results...")
            for _ in range(5):
                await results_container.evaluate("el => el.scrollBy(0, el.scrollHeight)")
                await asyncio.sleep(TIMING['scroll_delay'])
                
        except Exception as e:
            logger.debug(f"Error scrolling: {e}")
    
    async def extract_coordinates(self, page: Page) -> Tuple[Optional[float], Optional[float]]:
        """Extract latitude and longitude from URL or page content"""
        try:
            # Method 1: From URL
            url = page.url
            if '@' in url:
                coords_part = url.split('@')[1].split(',')
                if len(coords_part) >= 2:
                    lat = float(coords_part[0])
                    lon = float(coords_part[1])
                    logger.debug(f"Coordinates from URL: {lat}, {lon}")
                    return lat, lon
            
            # Method 2: From data attributes or meta tags
            lat_lon = await page.evaluate(r"""() => {
                // Try to find coordinates in meta tags
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
                
                // Try to find in page data
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
        
        # Filter out common false positives
        filtered_emails = set()
        exclude_patterns = [
            'example.com', 'test.com', 'domain.com', 
            'email.com', 'yourdomain.com', 'yoursite.com',
            'sentry.io', 'wixpress.com', 'schema.org',
            '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'
        ]
        
        for email in emails:
            email_lower = email.lower()
            if not any(pattern in email_lower for pattern in exclude_patterns):
                filtered_emails.add(email)
        
        return filtered_emails
    
    async def scrape_emails_from_google_maps(self, page: Page) -> Set[str]:
        """Extract emails directly from Google Maps listing"""
        emails = set()
        
        try:
            # Get all text content from the page
            page_text = await page.evaluate("() => document.body.innerText")
            emails.update(self.extract_emails_from_text(page_text))
            
            # Check specific sections that might contain emails
            selectors_to_check = [
                'div[role="main"]',
                'div.m6QErb',  # Info section
                'button[data-item-id]',  # Action buttons
                'a[href^="mailto:"]'  # Mailto links
            ]
            
            for selector in selectors_to_check:
                try:
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        text = await element.inner_text()
                        emails.update(self.extract_emails_from_text(text))
                        
                        # Check href for mailto
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
        """Visit business website and scrape for emails"""
        emails = set()
        
        if not website_url or 'google.com' in website_url:
            return emails
        
        page = None
        try:
            logger.info(f"Visiting website for emails: {website_url}")
            page = await context.new_page()
            
            # Set shorter timeout for website visits
            await page.goto(website_url, timeout=15000, wait_until='domcontentloaded')
            await asyncio.sleep(1)
            
            # Get page content
            page_text = await page.evaluate("() => document.body.innerText")
            page_html = await page.content()
            
            # Extract emails from text
            emails.update(self.extract_emails_from_text(page_text))
            emails.update(self.extract_emails_from_text(page_html))
            
            # Check common contact page patterns
            contact_links = await page.query_selector_all('a[href*="contact"], a[href*="about"], a[href*="team"]')
            
            for link in contact_links[:3]:  # Check first 3 contact-related links
                try:
                    href = await link.get_attribute('href')
                    if href and not href.startswith('mailto:'):
                        # Make absolute URL
                        if href.startswith('/'):
                            from urllib.parse import urljoin
                            href = urljoin(website_url, href)
                        
                        if href.startswith('http'):
                            await page.goto(href, timeout=10000, wait_until='domcontentloaded')
                            await asyncio.sleep(0.5)
                            
                            sub_text = await page.evaluate("() => document.body.innerText")
                            emails.update(self.extract_emails_from_text(sub_text))
                            
                            # Go back
                            await page.goto(website_url, timeout=10000, wait_until='domcontentloaded')
                except Exception:
                    continue
            
            if emails:
                logger.info(f"Found {len(emails)} email(s) on website: {', '.join(emails)}")
            else:
                logger.debug("No emails found on website")
                
        except Exception as e:
            logger.debug(f"Error scraping website for emails: {e}")
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
            
            # Wait for page to fully load
            await page.wait_for_load_state('networkidle', timeout=TIMING['networkidle_timeout'])
            
            # Check for blocking
            if await self.check_for_captcha(page):
                raise Exception("CAPTCHA detected during parsing")
            
            # Get the place URL
            place_url = page.url
            
            # Extract basic info
            name = await self.extract_text(page, SELECTORS['place_name'])
            if not name:
                logger.debug("Could not extract place name, skipping")
                return None
            
            # Get coordinates
            lat, lon = await self.extract_coordinates(page)
            
            # Check for duplicates
            if self.is_duplicate(name, lat, lon):
                logger.debug(f"Duplicate found: {name}")
                return None
            
            # Extract address
            address = await self.extract_text(page, SELECTORS['place_address'])
            
            # Extract phone
            phone = await self.extract_text(page, SELECTORS['place_phone'])
            
            # Extract emails from Google Maps page
            emails_from_maps = await self.scrape_emails_from_google_maps(page)
            
            # Extract website - check multiple locations
            website = await self.extract_attribute(page, SELECTORS['place_website'], 'href')
            
            # If no website found, check Menu tab
            if not website:
                try:
                    website = await page.evaluate("""() => {
                        // Look for Menu button/tab
                        let menuButtons = document.querySelectorAll('button[aria-label*="Menu"], button[data-item-id*="menu"]');
                        for (let btn of menuButtons) {
                            btn.click();
                        }
                        
                        // Wait a bit for menu content to load
                        return new Promise(resolve => {
                            setTimeout(() => {
                                // Look for website links in menu section
                                let links = document.querySelectorAll('a[href*="http"]');
                                for (let link of links) {
                                    let href = link.href;
                                    // Filter out Google/Maps links
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
            
            # Scrape emails from website if available
            emails_from_website = set()
            if website:
                emails_from_website = await self.scrape_emails_from_website(website, context)
            
            # Combine all emails
            all_emails = emails_from_maps.union(emails_from_website)
            email_string = ', '.join(sorted(all_emails)) if all_emails else None
            
            # Extract category
            category = await self.extract_text(page, SELECTORS['place_category'])
            
            # Extract rating - multiple methods
            rating = None
            try:
                rating = await page.evaluate(r"""() => {
                    // Method 1: Look for rating in common locations
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
                            // Extract number from text
                            let match = text.match(/(\d+\.?\d*)/);
                            if (match) {
                                let num = parseFloat(match[1]);
                                if (num >= 0 && num <= 5) {
                                    return num;
                                }
                            }
                        }
                    }
                    
                    // Method 2: Search all text for rating pattern
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
            
            # Extract hours - multiple methods
            hours = None
            try:
                hours = await page.evaluate("""() => {
                    // Method 1: Look for hours button/div
                    let hoursButton = document.querySelector('button[data-item-id*="oh"], button[aria-label*="Hours"]');
                    if (hoursButton) {
                        let text = hoursButton.getAttribute('aria-label') || hoursButton.textContent;
                        if (text) return text.trim();
                    }
                    
                    // Method 2: Look for hours in specific divs
                    let hoursDiv = document.querySelector('div[aria-label*="Hours"], div.t39EBf');
                    if (hoursDiv) {
                        return hoursDiv.textContent.trim();
                    }
                    
                    // Method 3: Look for "Open" or "Closed" status
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
            
            # Extract price level - multiple methods
            price = None
            try:
                # Method 1: From aria-label
                price = await self.extract_attribute(page, SELECTORS['place_price'], 'aria-label')
                
                # Method 2: Count dollar signs
                if not price:
                    price = await page.evaluate("""() => {
                        const priceSpans = document.querySelectorAll('span[aria-label*="Price"], span[aria-label*="price"]');
                        for (const span of priceSpans) {
                            const label = span.getAttribute('aria-label');
                            if (label && (label.includes('Price') || label.includes('price'))) {
                                return label;
                            }
                        }
                        
                        // Look for dollar signs
                        const dollarSigns = document.querySelector('span.mgr77e');
                        if (dollarSigns) {
                            return dollarSigns.textContent.trim();
                        }
                        return null;
                    }""")
                    
                logger.debug(f"Price level extracted: {price}")
            except Exception as e:
                logger.debug(f"Error extracting price: {e}")
            
            # Extract business status
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
        
        # Check by name first
        if name in self.seen_places:
            return True
        
        # Check by coordinates (within tolerance)
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
            
            for element in result_elements[:self.max_results * 2]:  # Get extra in case of duplicates
                try:
                    href = await element.get_attribute('href')
                    if href and '/maps/place/' in href:
                        links.append(href)
                except Exception:
                    continue
            
            logger.info(f"Found {len(links)} result links")
            return links
            
        except Exception as e:
            logger.error(f"Error collecting results: {e}")
            return []
    
    async def scrape_with_retry(self, max_retries: int = 3) -> List[Dict]:
        """Main scraping method with proxy rotation on failure"""
        retry_count = 0
        
        while retry_count < max_retries:
            browser = None
            context = None
            playwright = None
            
            try:
                # Get proxy for this attempt
                proxy = self.proxy_manager.get_next_proxy()
                
                # Setup browser
                browser, context, playwright = await self.setup_browser(proxy)
                page = await context.new_page()
                
                # Perform search
                if not await self.search_google_maps(page):
                    raise Exception("Search failed or blocked")
                
                # Collect result links
                result_links = await self.collect_results(page)
                
                if not result_links:
                    raise Exception("No results found")
                
                # Visit each place and scrape details
                for i, link in enumerate(result_links):
                    if len(self.scraped_places) >= self.max_results:
                        logger.info(f"Reached max results limit: {self.max_results}")
                        break
                    
                    try:
                        logger.info(f"Processing result {i+1}/{len(result_links)}")
                        await page.goto(link, timeout=TIMING['navigation_timeout'], wait_until='domcontentloaded')
                        await self.random_delay(2, 3)  # Give more time for content to load
                        
                        # Check for blocking
                        if await self.check_for_captcha(page):
                            raise Exception("CAPTCHA detected, rotating proxy")
                        
                        # Parse place details (pass context for website scraping)
                        place_data = await self.parse_place_details(page, context)
                        if place_data:
                            self.scraped_places.append(place_data)
                        
                        # Go back to results
                        await page.go_back(timeout=TIMING['navigation_timeout'])
                        await self.random_delay(0.5, 1)
                        
                    except Exception as e:
                        logger.warning(f"Error processing result {i+1}: {e}")
                        if "CAPTCHA" in str(e):
                            raise  # Re-raise to trigger proxy rotation
                        continue
                
                # Success - return results
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
                # Proper cleanup to avoid Windows pipe errors
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


def save_results(places: List[Dict], keyword: str, location: str):
    """Save results to CSV and JSON files"""
    if not places:
        logger.warning("No results to save")
        return
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_keyword = keyword.replace(' ', '_')
    safe_location = location.replace(' ', '_')
    base_filename = f"results_{safe_keyword}_{safe_location}_{timestamp}"
    
    # Save as CSV
    csv_filename = f"{base_filename}.csv"
    try:
        with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
            if places:
                writer = csv.DictWriter(f, fieldnames=places[0].keys())
                writer.writeheader()
                writer.writerows(places)
        logger.info(f"Saved {len(places)} results to {csv_filename}")
    except Exception as e:
        logger.error(f"Error saving CSV: {e}")
    
    # Save as JSONL
    jsonl_filename = f"{base_filename}.jsonl"
    try:
        with open(jsonl_filename, 'w', encoding='utf-8') as f:
            for place in places:
                f.write(json.dumps(place) + '\n')
        logger.info(f"Saved {len(places)} results to {jsonl_filename}")
    except Exception as e:
        logger.error(f"Error saving JSONL: {e}")


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Google Maps Scraper with Playwright',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic search (headful mode for debugging)
  python scraper.py --keyword "cafe" --location "New York" --max 10
  
  # Headless mode with proxies
  python scraper.py --keyword "gym" --location "90210" --max 20 --headless true --proxy-file proxies.txt
  
  # Full featured search
  python scraper.py --keyword "restaurant" --location "Los Angeles" --max 50 --headless false --proxy-file proxies.txt
        """
    )
    
    parser.add_argument('--keyword', required=True, help='Search keyword (e.g., "cafe", "gym")')
    parser.add_argument('--location', required=True, help='Location (city name or zip code)')
    parser.add_argument('--max', type=int, default=10, help='Maximum number of places to scrape (default: 10)')
    parser.add_argument('--headless', type=str, default='false', choices=['true', 'false'], 
                       help='Run in headless mode (default: false)')
    parser.add_argument('--proxy-file', type=str, help='Path to proxy file (format: ip:port:username:password)')
    
    args = parser.parse_args()
    
    # Convert headless string to boolean
    headless = args.headless.lower() == 'true'
    
    logger.info("="*60)
    logger.info("Google Maps Scraper Started")
    logger.info(f"Keyword: {args.keyword}")
    logger.info(f"Location: {args.location}")
    logger.info(f"Max Results: {args.max}")
    logger.info(f"Headless: {headless}")
    logger.info(f"Proxy File: {args.proxy_file or 'None'}")
    logger.info("="*60)
    
    # Initialize proxy manager
    proxy_manager = ProxyManager(args.proxy_file)
    
    # Initialize scraper
    scraper = PlaceScraper(
        keyword=args.keyword,
        location=args.location,
        max_results=args.max,
        headless=headless,
        proxy_manager=proxy_manager
    )
    
    # Run scraper
    results = await scraper.scrape_with_retry(max_retries=3)
    
    # Save results
    save_results(results, args.keyword, args.location)
    
    logger.info("="*60)
    logger.info(f"Scraping completed! Total results: {len(results)}")
    logger.info("="*60)


if __name__ == "__main__":
    asyncio.run(main())
