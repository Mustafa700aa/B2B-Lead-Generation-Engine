"""
Main Entrypoint and Pipeline Orchestrator for the B2B Lead Generation Engine.
Coordinates Scraping (Playwright) -> Enrichment (HTTPX + Regex) -> Export (Pandas + OpenPyXL)
with full SQLite checkpointing and error resilience.
"""

import asyncio
import argparse
import sys
from pathlib import Path

from config import (
    DEFAULT_SEARCH_QUERY,
    DEFAULT_MAX_RESULTS,
    DEFAULT_HEADLESS,
    EXPORTS_DIR,
    DB_PATH,
    LOG_FILE_PATH,
)
from database import DatabaseManager
from scraper import GoogleMapsScraper
from enricher import DataEnricher
from exporter import DataExporter
from logger import get_logger

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logger = get_logger("MainPipeline")


def print_banner():
    banner = """
==================================================================
                 B2B LEAD GENERATION ENGINE
        Google Maps (Playwright) + Async Enricher + Pandas
==================================================================
    """
    print(banner)


async def run_pipeline(
    query: str = DEFAULT_SEARCH_QUERY,
    limit: int = DEFAULT_MAX_RESULTS,
    headless: bool = DEFAULT_HEADLESS,
    skip_enrich: bool = False,
    skip_scrape: bool = False,
    output_filename: str = None,
):
    """
    Execute the end-to-end B2B Lead Generation Pipeline.
    """
    print_banner()
    logger.info("Initializing Lead Generation Engine components...")
    
    # 1. Initialize Database
    db = DatabaseManager(DB_PATH)
    logger.info(f"Database connected at: {DB_PATH}")

    # 2. Phase 1: Scraping (Google Maps via Playwright)
    if not skip_scrape:
        logger.info(f"\n--- [1/3] SCRAPING GOOGLE MAPS ---")
        scraper = GoogleMapsScraper(db=db, headless=headless, max_results=limit)
        scraped_leads = await scraper.scrape(query=query)
        logger.info(f"Scraped and checkpointed {len(scraped_leads)} leads.")
    else:
        logger.info("Skipping scrape phase (re-using database records).")

    # 3. Phase 2: Contact Intelligence & Enrichment (Async HTTP + Regex)
    if not skip_enrich:
        logger.info(f"\n--- [2/3] ENRICHING CONTACT EMAILS ---")
        enricher = DataEnricher(db=db)
        await enricher.enrich_all()
    else:
        logger.info("Skipping email enrichment phase as requested.")

    # 4. Phase 3: Data Cleaning & Formatted Excel Export (Pandas + OpenPyXL)
    logger.info(f"\n--- [3/3] EXPORTING & FORMATTING DATASET ---")
    exporter = DataExporter(db=db)
    
    try:
        export_file = exporter.export_to_excel(output_filename=output_filename)
        logger.info(f"Report successfully generated at: {export_file}")
    except ValueError as e:
        logger.error(f"Export failed: {e}")
        return

    # 5. Summary Statistics
    stats = db.get_lead_stats()
    print("\n" + "=" * 65)
    print("                    PIPELINE EXECUTION SUMMARY                   ")
    print("=" * 65)
    print(f" Total Leads in Database : {stats['total_leads']}")
    print(f" Leads with Phone Numbers: {stats['leads_with_phone']}")
    print(f" Leads with Websites     : {stats['leads_with_website']}")
    print(f" Enriched Leads          : {stats['enriched_leads']}")
    print(f" Verified Contact Emails : {stats['leads_with_email']}")
    print(f" Output Excel Report     : {export_file}")
    print(f" Execution Log File      : {LOG_FILE_PATH}")
    print("=" * 65 + "\n")


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="B2B Lead Generation Engine (Playwright + Pandas + SQLite + HTTPX)"
    )
    parser.add_argument(
        "--query", "-q",
        type=str,
        default=DEFAULT_SEARCH_QUERY,
        help=f"Search query for Google Maps (default: '{DEFAULT_SEARCH_QUERY}')"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=5,
        help=f"Maximum number of leads to scrape (default: 5)"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Run browser in headless mode (default: False for visible debugging)"
    )
    parser.add_argument(
        "--skip-enrich",
        action="store_true",
        default=False,
        help="Skip website visiting and email enrichment"
    )
    parser.add_argument(
        "--skip-scrape",
        action="store_true",
        default=False,
        help="Skip Google Maps scraping and process existing database leads"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Custom Excel output filename"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()
    asyncio.run(
        run_pipeline(
            query=args.query,
            limit=args.limit,
            headless=args.headless,
            skip_enrich=args.skip_enrich,
            skip_scrape=args.skip_scrape,
            output_filename=args.output,
        )
    )
