"""
Configuration and settings module for the B2B Lead Generation Engine.
Manages file paths, scraping parameters, anti-ban settings, DOM selectors,
proxy configurations, and enrichment policies.
"""

import os
from pathlib import Path
from typing import List, Dict, Any

# ==============================================================================
# DIRECTORY & FILE PATHS
# ==============================================================================
BASE_DIR: Path = Path(__file__).resolve().parent
DATA_DIR: Path = BASE_DIR / "data"
LOGS_DIR: Path = DATA_DIR / "logs"
EXPORTS_DIR: Path = DATA_DIR / "exports"
DB_PATH: Path = DATA_DIR / "leads.db"
LOG_FILE_PATH: Path = LOGS_DIR / "b2b_lead_engine.log"

# Auto-ensure directories exist on module import
for directory in (DATA_DIR, LOGS_DIR, EXPORTS_DIR):
    directory.mkdir(parents=True, exist_ok=True)

# ==============================================================================
# LOGGING CONFIGURATION
# ==============================================================================
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 10 MB rotating file limit
LOG_BACKUP_COUNT: int = 5
LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | [%(name)s] %(message)s"
LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

# ==============================================================================
# ANTI-BAN & STEALTH PROXY CONFIGURATION
# ==============================================================================
# Add your rotating or residential proxy endpoints here (e.g., "http://user:pass@gate.proxy.com:8080")
PROXIES: List[str] = [
    # os.getenv("RESIDENTIAL_PROXY_1", ""),
    # os.getenv("RESIDENTIAL_PROXY_2", ""),
]
ROTATE_PROXIES: bool = os.getenv("ROTATE_PROXIES", "false").lower() == "true"

# Realistic Modern Desktop User Agents for anti-fingerprinting
USER_AGENTS: List[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

DEFAULT_VIEWPORT: Dict[str, int] = {"width": 1920, "height": 1080}
DEFAULT_LOCALE: str = "en-US"
DEFAULT_TIMEZONE: str = "Asia/Dubai"

CHROMIUM_ARGS: List[str] = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-infobars",
    "--disable-dev-shm-usage",
    "--disable-extensions",
    "--lang=en-US",
]

# ==============================================================================
# SCRAPER SETTINGS & SPONSORED FILTER
# ==============================================================================
DEFAULT_SEARCH_QUERY: str = "Real Estate Agencies in Dubai"
DEFAULT_MAX_RESULTS: int = 50
DEFAULT_HEADLESS: bool = False  # Headed mode recommended for reliable Google Maps rendering
PAGE_NAVIGATION_TIMEOUT_MS: int = 45000
ELEMENT_WAIT_TIMEOUT_MS: int = 5000
SCROLL_PAUSE_SECONDS: float = 2.0
MAX_SCROLL_RETRIES: int = 6

# Sponsored Ads Skipping Logic
SKIP_SPONSORED: bool = True
SPONSORED_TEXT_MARKERS: List[str] = [
    "sponsored",
    "ad",
    "anzeige",
    "publicidad",
    "sponsorisé",
    "إعلان",
    "annuncio",
]

# ==============================================================================
# GOOGLE MAPS DOM SELECTORS
# ==============================================================================
SELECTORS: Dict[str, Any] = {
    # Consent dialogs / Cookie consent
    "consent_buttons": [
        "button[aria-label*='Accept all']",
        "form[action*='consent'] button",
        "button:has-text('Accept all')",
        "button:has-text('I agree')",
        "button:has-text('Agree')",
        "button:has-text('Accept')",
    ],
    # Feed & Results
    "feed_container": "div[role='feed']",
    "result_item": "div[role='feed'] > div > div:has(a[href*='/maps/place/']), div[role='article'], div.Nv2PK",
    "item_link": "a.hfpxzc, a[href*='/maps/place/']",
    "item_title_preview": "div.qBF1Pd, div.fontHeadlineSmall",
    "end_of_results_marker": "span:has-text(\"You've reached the end of the list.\"), div.HlvSq",
    
    # Detail Panel Elements
    "title": "h1.DUwDvf, h1.fontHeadlineLarge, div.fontHeadlineSmall, h1",
    "sponsored_badge": "span.k3708d, div.k3708d, span[aria-label*='Sponsored'], span:has-text('Sponsored'), span:has-text('Ad')",
    "rating": "div.F7nice span[aria-hidden='true'], span.MW4etd, span.fontBodyMedium > span[aria-hidden='true']",
    "reviews_count": "div.F7nice span[aria-label*='review'], span.UY7F9, span.fontBodyMedium span[aria-label*='review']",
    
    # Contact & Action Buttons in Details Panel
    "phone_button": "button[data-item-id*='phone:tel:'], button[data-tooltip*='phone'], button[aria-label*='Phone:']",
    "address_button": "button[data-item-id*='address'], button[data-tooltip*='address'], button[aria-label*='Address:']",
    "website_button": "a[data-item-id='authority'], a[aria-label*='Website:'], a[data-tooltip*='website']",
}

# ==============================================================================
# DATA ENRICHER (EMAIL EXTRACTOR) SETTINGS
# ==============================================================================
ENRICH_TIMEOUT_SECONDS: int = 15
MAX_CONCURRENT_ENRICH_REQUESTS: int = 10
MAX_SUBPAGES_TO_SEARCH: int = 4

CONTACT_PAGE_SLUGS: List[str] = [
    "/contact",
    "/contact-us",
    "/contactus",
    "/about",
    "/about-us",
    "/reach-us",
    "/get-in-touch",
    "/connect",
]

# Noise email extensions & placeholder blacklist
IGNORED_EMAIL_EXTENSIONS: List[str] = [
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
    ".ico", ".bmp", ".tiff", ".css", ".js", ".woff", ".woff2"
]

IGNORED_EMAIL_PATTERNS: List[str] = [
    "example.com", "domain.com", "yoursite.com", "sentry.io",
    "wixpress.com", "cloudflare.com", "schema.org", "w3.org",
    "email.com", "test.com"
]

# ==============================================================================
# DATA EXPORTER SETTINGS
# ==============================================================================
EXCEL_SHEET_NAME: str = "B2B Leads"
EXCEL_HEADER_BG_COLOR: str = "1F4E79"  # Deep Slate Navy
EXCEL_HEADER_FONT_COLOR: str = "FFFFFF"  # White
EXCEL_ROW_ALT_BG_COLOR: str = "F2F5F9"  # Soft Ice Blue
