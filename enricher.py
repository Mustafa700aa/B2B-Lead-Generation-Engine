"""
Data Enrichment module for the B2B Lead Generation Engine.
Visits company websites asynchronously, performs deep contact-page discovery,
and extracts verified email addresses using regex patterns.
"""

import asyncio
import re
from typing import List, Optional, Set
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup

from config import (
    ENRICH_TIMEOUT_SECONDS,
    MAX_CONCURRENT_ENRICH_REQUESTS,
    CONTACT_PAGE_SLUGS,
    IGNORED_EMAIL_EXTENSIONS,
    IGNORED_EMAIL_PATTERNS,
    USER_AGENTS,
)
from models import Lead
from database import DatabaseManager
from logger import get_logger

logger = get_logger("DataEnricher")

# RFC 5322-compliant email matching pattern
EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
    re.IGNORECASE
)


class DataEnricher:
    """
    Asynchronous website visit and contact intelligence engine.
    Extracts, validates, and prioritizes email addresses for business leads.
    """

    def __init__(
        self,
        db: Optional[DatabaseManager] = None,
        max_concurrency: int = MAX_CONCURRENT_ENRICH_REQUESTS,
        timeout: int = ENRICH_TIMEOUT_SECONDS,
    ):
        self.db = db or DatabaseManager()
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.timeout = timeout
        self.headers = {
            "User-Agent": USER_AGENTS[0],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

    def _clean_and_filter_emails(self, raw_emails: Set[str], domain: str) -> List[str]:
        """
        Filter out tracking scripts, images, placeholders, and dummy email artifacts.
        """
        valid_emails = []

        for email in raw_emails:
            email_lower = email.lower().strip().rstrip(".")

            # Discard invalid lengths
            if len(email_lower) < 6 or len(email_lower) > 80:
                continue

            # Discard image extensions (e.g. logo@2x.png)
            if any(email_lower.endswith(ext) for ext in IGNORED_EMAIL_EXTENSIONS):
                continue

            # Discard placeholder and noise domains
            if any(pattern in email_lower for pattern in IGNORED_EMAIL_PATTERNS):
                continue

            # Ensure valid structure
            parts = email_lower.split("@")
            if len(parts) != 2:
                continue

            user_part, domain_part = parts
            if not user_part or "." not in domain_part:
                continue

            valid_emails.append(email_lower)

        # Deduplicate preserving order
        unique_emails = list(dict.fromkeys(valid_emails))

        # Prioritize primary business inboxes (info@, contact@, sales@, hello@, support@)
        priority_prefixes = ("info@", "contact@", "sales@", "hello@", "support@", "enquiry@", "office@")
        unique_emails.sort(
            key=lambda e: 0 if any(e.startswith(p) for p in priority_prefixes) else 1
        )

        return unique_emails

    async def _fetch_html(self, client: httpx.AsyncClient, url: str) -> Optional[str]:
        """
        Fetch HTML content from a URL with timeout and redirect handling.
        """
        try:
            response = await client.get(url, timeout=self.timeout, follow_redirects=True)
            if response.status_code == 200 and "text/html" in response.headers.get("content-type", ""):
                return response.text
        except httpx.TimeoutException:
            logger.debug(f"Timeout connecting to {url}")
        except httpx.HTTPError as e:
            logger.debug(f"HTTP error for {url}: {e}")
        except Exception as e:
            logger.debug(f"Connection error for {url}: {e}")
        return None

    def _extract_emails_from_html(self, html: str) -> Set[str]:
        """
        Extract email addresses from HTML text and mailto: anchor links.
        """
        found_emails = set()
        try:
            soup = BeautifulSoup(html, "html.parser")

            # 1. Search mailto: links
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if href.startswith("mailto:"):
                    clean_mail = href.replace("mailto:", "").split("?")[0].strip()
                    if clean_mail:
                        found_emails.add(clean_mail)

            # 2. Search regex in plain text
            text_content = soup.get_text(separator=" ")
            matches = EMAIL_REGEX.findall(text_content)
            for m in matches:
                found_emails.add(m)

            # 3. Search regex in HTML attributes
            for attr_match in EMAIL_REGEX.findall(html):
                found_emails.add(attr_match)

        except Exception as e:
            logger.debug(f"Error parsing HTML for emails: {e}")

        return found_emails

    def _find_contact_links(self, html: str, base_url: str) -> List[str]:
        """
        Identify internal links leading to contact, about, or support pages.
        """
        contact_urls = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            base_domain = urlparse(base_url).netloc

            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                text = a.get_text(strip=True).lower()
                href_lower = href.lower()

                # Check if text or URL contains contact keywords
                is_contact = any(
                    kw in href_lower or kw in text
                    for kw in ["contact", "about", "reach-us", "touch", "team"]
                )

                if is_contact:
                    full_url = urljoin(base_url, href)
                    parsed = urlparse(full_url)
                    # Keep only same-domain URLs
                    if parsed.netloc == base_domain and parsed.scheme in ("http", "https"):
                        if full_url not in contact_urls:
                            contact_urls.append(full_url)
        except Exception:
            pass

        return contact_urls[:4]

    async def enrich_lead(self, client: httpx.AsyncClient, lead: Lead) -> Optional[str]:
        """
        Enrich a single lead by visiting its website, searching the homepage,
        and optionally crawling contact subpages.

        :param client: Shared httpx AsyncClient
        :param lead: Lead instance to enrich
        :return: Discovered email or None
        """
        if not lead.website:
            return None

        url = lead.website.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        domain = urlparse(url).netloc
        all_raw_emails: Set[str] = set()

        async with self.semaphore:
            logger.debug(f"Visiting [{lead.name}] website: {url}")
            
            # Step 1: Fetch Homepage
            homepage_html = await self._fetch_html(client, url)
            if homepage_html:
                all_raw_emails.update(self._extract_emails_from_html(homepage_html))

            # Step 2: If no email found, crawl contact subpages
            if not all_raw_emails and homepage_html:
                contact_links = self._find_contact_links(homepage_html, url)
                
                # Fallback to standard contact slugs if no links detected
                if not contact_links:
                    contact_links = [urljoin(url, slug) for slug in CONTACT_PAGE_SLUGS[:3]]

                # Fetch subpages concurrently
                subpage_tasks = [self._fetch_html(client, sub_url) for sub_url in contact_links]
                subpage_results = await asyncio.gather(*subpage_tasks, return_exceptions=True)

                for result in subpage_results:
                    if isinstance(result, str) and result:
                        all_raw_emails.update(self._extract_emails_from_html(result))

            # Filter and rank emails
            clean_emails = self._clean_and_filter_emails(all_raw_emails, domain)
            best_email = clean_emails[0] if clean_emails else None

            # Checkpoint directly to SQLite database
            if lead.id:
                self.db.mark_lead_enriched(lead.id, best_email)
                lead.email = best_email
                lead.is_enriched = True

            if best_email:
                logger.info(f"Successfully enriched [{lead.name}] -> Email: {best_email}")
            else:
                logger.debug(f"No email found for [{lead.name}] ({url})")

            return best_email

    async def enrich_all(self, leads: Optional[List[Lead]] = None) -> List[Lead]:
        """
        Enrich a batch of leads (or all unenriched leads in SQLite database) concurrently.

        :param leads: Optional list of Lead objects. If None, queries DB for unenriched leads.
        :return: List of enriched leads
        """
        target_leads = leads if leads is not None else self.db.get_unenriched_leads()

        if not target_leads:
            logger.info("No unenriched leads with website URLs found.")
            return []

        logger.info(f"Starting async email enrichment for {len(target_leads)} leads...")

        limits = httpx.Limits(max_keepalive_connections=20, max_connections=50)
        async with httpx.AsyncClient(headers=self.headers, verify=False, limits=limits) as client:
            tasks = [self.enrich_lead(client, lead) for lead in target_leads]
            await asyncio.gather(*tasks, return_exceptions=True)

        logger.info(f"Enrichment completed for {len(target_leads)} leads.")
        return target_leads
