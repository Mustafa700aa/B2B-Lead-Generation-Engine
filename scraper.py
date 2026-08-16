"""
Google Maps Scraper module using Playwright.
Handles search queries, infinite feed scrolling, sponsored ad filtering,
and detail extraction with immediate SQLite checkpointing.
"""

import asyncio
import random
import re
import urllib.parse
from typing import List, Optional
from playwright.async_api import async_playwright, Page, BrowserContext, ElementHandle

from config import (
    SELECTORS,
    USER_AGENTS,
    DEFAULT_VIEWPORT,
    DEFAULT_LOCALE,
    DEFAULT_TIMEZONE,
    CHROMIUM_ARGS,
    PAGE_NAVIGATION_TIMEOUT_MS,
    ELEMENT_WAIT_TIMEOUT_MS,
    SCROLL_PAUSE_SECONDS,
    MAX_SCROLL_RETRIES,
    SKIP_SPONSORED,
    SPONSORED_TEXT_MARKERS,
)
from models import Lead
from database import DatabaseManager
from logger import get_logger

logger = get_logger("GoogleMapsScraper")


class GoogleMapsScraper:
    """
    Object-Oriented Google Maps Scraper leveraging Playwright to extract
    business listings with robust anti-bot measures and live checkpointing.
    """

    def __init__(
        self,
        db: Optional[DatabaseManager] = None,
        headless: bool = False,
        max_results: int = 20,
    ):
        self.db = db or DatabaseManager()
        self.headless = headless
        self.max_results = max_results
        self.user_agent = random.choice(USER_AGENTS)

    async def _handle_consent_dialog(self, page: Page) -> None:
        """Dismiss Google cookies or consent dialogs if present."""
        for selector in SELECTORS["consent_buttons"]:
            try:
                button = page.locator(selector).first
                if await button.is_visible(timeout=1500):
                    await button.click()
                    logger.info("Dismissed Google consent dialog.")
                    await asyncio.sleep(1.0)
                    break
            except Exception:
                continue

    async def _is_sponsored(self, card_element: ElementHandle, page: Page) -> bool:
        """
        Check whether a listing item is a Sponsored Ad based on badges, URLs, and text markers.
        """
        if not SKIP_SPONSORED:
            return False

        try:
            # Check for ad click tracking URL in any link
            links = await card_element.query_selector_all("a")
            for link in links:
                href = await link.get_attribute("href") or ""
                if any(ad_pattern in href for ad_pattern in ("/aclk", "adurl", "googleadservices", "/pagead/")):
                    return True

            # Check for sponsored badge elements inside the card
            badge_selector = SELECTORS.get("sponsored_badge", "span.k3708d")
            badge = await card_element.query_selector(badge_selector)
            if badge and await badge.is_visible():
                return True

            # Check full card text content for sponsored markers
            card_text = (await card_element.inner_text() or "").lower()
            lines = [l.strip().lower() for l in card_text.splitlines() if l.strip()]
            for marker in SPONSORED_TEXT_MARKERS:
                marker_lower = marker.lower()
                if marker_lower in lines or any(marker_lower == word for line in lines for word in line.split()):
                    return True
        except Exception:
            pass

        return False

    async def _extract_detail_panel(self, page: Page, query: str, expected_name: Optional[str] = None) -> Optional[Lead]:
        """
        Extract structured business information from the active Google Maps detail panel.
        """
        try:
            # Allow detail panel to render
            await asyncio.sleep(1.0)

            # 1. Company Name
            name: Optional[str] = expected_name
            title_selectors = [
                "h1.DUwDvf",
                "h1.fontHeadlineLarge",
                "div.fontHeadlineSmall",
                "div[role='main'] h1",
            ]
            for sel in title_selectors:
                el = await page.query_selector(sel)
                if el:
                    text = (await el.inner_text() or "").strip()
                    if text and text.lower() not in ["results", "search results"]:
                        name = text
                        break

            if not name:
                return None

            # 2. Rating & Reviews Count
            rating: Optional[float] = None
            reviews_count: Optional[int] = None
            try:
                rating_el = await page.query_selector("div.F7nice span[aria-hidden='true'], span.MW4etd, span.ceWZyc span.MW4etd")
                if rating_el:
                    rating_str = (await rating_el.inner_text() or "").replace(",", ".").strip()
                    match = re.search(r"(\d+\.?\d*)", rating_str)
                    if match:
                        rating = float(match.group(1))

                reviews_el = await page.query_selector("div.F7nice span[aria-label*='review'], span.UY7F9, span[aria-label*='reviews']")
                if reviews_el:
                    rev_text = await reviews_el.inner_text() or ""
                    rev_digits = re.sub(r"[^\d]", "", rev_text)
                    if rev_digits:
                        reviews_count = int(rev_digits)
            except Exception as e:
                logger.debug(f"Could not parse rating/reviews for '{name}': {e}")

            # 3. Address
            address: Optional[str] = None
            try:
                addr_selectors = [
                    "button[data-item-id*='address']",
                    "button[data-tooltip*='address']",
                    "button[aria-label*='Address:']",
                    "button[data-item-id='address']",
                    "button[aria-label*='address']",
                ]
                for sel in addr_selectors:
                    addr_btn = await page.query_selector(sel)
                    if addr_btn:
                        aria = await addr_btn.get_attribute("aria-label") or ""
                        text = (await addr_btn.inner_text() or "").strip()
                        if aria and "address:" in aria.lower():
                            address = re.sub(r"(?i)address:\s*", "", aria).strip()
                        elif text:
                            address = text
                        if address:
                            break
            except Exception as e:
                logger.debug(f"Could not extract address for '{name}': {e}")

            # 4. Phone Number
            phone: Optional[str] = None
            try:
                phone_selectors = [
                    "button[data-item-id*='phone:tel:']",
                    "button[data-tooltip*='phone']",
                    "button[aria-label*='Phone:']",
                    "button[data-item-id*='phone']",
                    "button[aria-label*='phone']",
                ]
                for sel in phone_selectors:
                    phone_btn = await page.query_selector(sel)
                    if phone_btn:
                        item_id = await phone_btn.get_attribute("data-item-id") or ""
                        aria = await phone_btn.get_attribute("aria-label") or ""
                        text = (await phone_btn.inner_text() or "").strip()
                        if "phone:tel:" in item_id:
                            phone = item_id.split("phone:tel:")[-1].strip()
                        elif "phone:" in aria.lower():
                            phone = re.sub(r"(?i)phone:\s*", "", aria).strip()
                        elif text:
                            phone = text
                        if phone:
                            break

                # Fallback phone search in detail panel text
                if not phone:
                    panel_text = await page.evaluate("() => document.querySelector('div[role=\"main\"]')?.innerText || ''")
                    phone_matches = re.findall(r"(\+?\d{1,4}[\s\-]?(?:\(\d{1,4}\)[\s\-]?)?[\d\s\-]{6,14}\d)", panel_text)
                    for pm in phone_matches:
                        clean_pm = pm.strip()
                        if len(re.sub(r"\D", "", clean_pm)) >= 7:
                            phone = clean_pm
                            break
            except Exception as e:
                logger.debug(f"Could not extract phone for '{name}': {e}")

            # 5. Website URL
            website: Optional[str] = None
            try:
                web_selectors = [
                    "a[data-item-id='authority']",
                    "a[aria-label*='Website:']",
                    "a[data-tooltip*='website']",
                    "a[aria-label*='website']",
                    "a[data-tooltip*='Open website']",
                ]
                for sel in web_selectors:
                    web_btn = await page.query_selector(sel)
                    if web_btn:
                        href = await web_btn.get_attribute("href")
                        if href and not href.startswith("javascript"):
                            # Unwrap google redirect URLs if present
                            if "google.com/url?" in href:
                                parsed = urllib.parse.urlparse(href)
                                qs = urllib.parse.parse_qs(parsed.query)
                                website = qs.get("q", [href])[0]
                            elif href.startswith("http"):
                                website = href
                            if website:
                                break
            except Exception as e:
                logger.debug(f"Could not extract website for '{name}': {e}")

            # 6. Current Maps URL
            maps_url = page.url

            lead = Lead(
                name=name,
                phone=phone,
                address=address,
                website=website,
                query=query,
                rating=rating,
                reviews_count=reviews_count,
                maps_url=maps_url,
                is_enriched=False,
            )
            return lead

        except Exception as e:
            logger.error(f"Error parsing detail panel: {e}", exc_info=True)
            return None

    async def scrape(self, query: str) -> List[Lead]:
        """
        Execute full scraping workflow for the specified search query.
        Results are immediately checkpointed to SQLite database.

        :param query: Google Maps search query (e.g. 'Real Estate Agencies in Dubai')
        :return: List of scraped Lead objects
        """
        logger.info(f"Starting Google Maps Scraping for query: '{query}' (Target: {self.max_results} leads)")
        scraped_leads: List[Lead] = []
        seen_identifiers = set()

        async with async_playwright() as p:
            browser = None
            try:
                browser = await p.chromium.launch(
                    headless=self.headless,
                    args=CHROMIUM_ARGS,
                )
            except Exception as launch_err:
                logger.warning(f"Standard Chromium launch notice ({launch_err}). Attempting system browser (Edge/Chrome)...")
                for channel in ("msedge", "chrome"):
                    try:
                        browser = await p.chromium.launch(
                            headless=self.headless,
                            args=CHROMIUM_ARGS,
                            channel=channel,
                        )
                        logger.info(f"Successfully launched browser using channel: '{channel}'")
                        break
                    except Exception:
                        continue
                if not browser:
                    raise RuntimeError("Could not launch any Chromium or system browser.")
            context: BrowserContext = await browser.new_context(
                user_agent=self.user_agent,
                viewport=DEFAULT_VIEWPORT,
                locale=DEFAULT_LOCALE,
                timezone_id=DEFAULT_TIMEZONE,
            )
            page: Page = await context.new_page()
            page.set_default_timeout(PAGE_NAVIGATION_TIMEOUT_MS)

            try:
                # 1. Navigate directly to Google Maps Search URL
                encoded_query = urllib.parse.quote_plus(query)
                search_url = f"https://www.google.com/maps/search/{encoded_query}?hl=en"
                logger.info(f"Navigating to Google Maps Search: {search_url}")
                
                await page.goto(search_url, wait_until="domcontentloaded")
                await self._handle_consent_dialog(page)
                await asyncio.sleep(2.5)

                # 2. Wait for Results Feed container or result items
                feed_selector = SELECTORS["feed_container"]
                try:
                    await page.wait_for_selector(
                        f"{feed_selector}, {SELECTORS['item_link']}, div.Nv2PK",
                        timeout=15000
                    )
                except Exception:
                    logger.warning("Feed selector wait timed out. Checking rendered items directly...")

                # 3. Phase A: Collect unique place links from the search feed
                logger.info(f"Collecting place listings from search feed (Target: {self.max_results})...")
                collected_items = []
                scroll_retries = 0

                while len(collected_items) < self.max_results and scroll_retries < MAX_SCROLL_RETRIES:
                    links = await page.query_selector_all("a.hfpxzc, a[href*='/maps/place/']")
                    new_found = False

                    for link in links:
                        if len(collected_items) >= self.max_results:
                            break

                        try:
                            href = (await link.get_attribute("href") or "").strip()
                            aria_name = (await link.get_attribute("aria-label") or "").strip()

                            if not href or not aria_name:
                                continue

                            # Skip sponsored / ad-tracking URLs
                            if any(p in href for p in ("/aclk", "adurl", "googleadservices", "/pagead/")):
                                logger.info(f"Skipping Ad URL in feed: '{aria_name}'")
                                continue

                            # Skip if URL doesn't look like a real place page
                            if "/maps/place/" not in href:
                                continue

                            # Deduplicate by place name / href
                            identifier = aria_name.lower()
                            if identifier in seen_identifiers:
                                continue

                            seen_identifiers.add(identifier)
                            collected_items.append({"name": aria_name, "url": href})
                            new_found = True
                            logger.info(f"Discovered listing ({len(collected_items)}/{self.max_results}): '{aria_name}'")

                        except Exception as e:
                            logger.debug(f"Error inspecting feed link: {e}")
                            continue

                    if len(collected_items) >= self.max_results:
                        break

                    # Scroll feed down to load more results
                    feed_element = await page.query_selector(feed_selector)
                    if feed_element:
                        await feed_element.evaluate("el => el.scrollBy(0, 1500)")
                    else:
                        await page.mouse.wheel(0, 1500)

                    await asyncio.sleep(SCROLL_PAUSE_SECONDS)

                    if not new_found:
                        scroll_retries += 1
                        logger.debug(f"Scroll retry {scroll_retries}/{MAX_SCROLL_RETRIES}")
                    else:
                        scroll_retries = 0

                    end_marker = await page.query_selector(SELECTORS["end_of_results_marker"])
                    if end_marker and await end_marker.is_visible():
                        logger.info("Reached end of Google Maps feed.")
                        break

                logger.info(f"Feed collection complete. Found {len(collected_items)} unique places. Now extracting full details...")

                # 4. Phase B: Visit each place and extract full intelligence
                for idx, item in enumerate(collected_items, start=1):
                    place_name = item["name"]
                    place_url = item["url"]

                    try:
                        logger.info(f"[{idx}/{len(collected_items)}] Extracting details for: '{place_name}'")
                        await page.goto(place_url, wait_until="domcontentloaded")

                        # Wait for the detail panel title to render (NOT networkidle — Google Maps SPA never idles)
                        try:
                            await page.wait_for_selector(
                                "h1.DUwDvf, h1.fontHeadlineLarge, div[role='main'] h1",
                                timeout=8000,
                            )
                        except Exception:
                            logger.debug(f"Detail title selector not found for '{place_name}', proceeding with fallback extraction.")

                        await asyncio.sleep(2.0)

                        lead = await self._extract_detail_panel(page, query, expected_name=place_name)
                        if not lead or not lead.name:
                            lead = Lead(
                                name=place_name,
                                query=query,
                                maps_url=place_url,
                                is_enriched=False,
                            )

                        lead.maps_url = place_url

                        # Checkpoint immediately to SQLite
                        lead_id = self.db.save_lead(lead)
                        lead.id = lead_id
                        scraped_leads.append(lead)

                        logger.info(
                            f"[{idx}/{len(collected_items)}] Checkpointed: '{lead.name}' | Phone: {lead.phone or 'N/A'} | Web: {lead.website or 'N/A'}"
                        )

                    except Exception as item_err:
                        logger.warning(f"Could not extract details for '{place_name}': {item_err}")
                        fallback_lead = Lead(name=place_name, query=query, maps_url=place_url, is_enriched=False)
                        lead_id = self.db.save_lead(fallback_lead)
                        fallback_lead.id = lead_id
                        scraped_leads.append(fallback_lead)

            except Exception as e:
                logger.error(f"Critical error during Google Maps scraping: {e}", exc_info=True)
            finally:
                await context.close()
                await browser.close()

        logger.info(f"Scraping completed. Total leads checkpointed: {len(scraped_leads)}")
        return scraped_leads
