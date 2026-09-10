"""Pipeline CLI entrypoint for multimodal data ingestion.

Supports local execution, debugging, and manual backfills across:
  1. Open-Meteo macro climatic metrics.
  2. Competitor pricing scrapers (Red Bull & Monster Energy).
  3. Legacy partner warehouse inventory extracts.

Provides `--source` and `--dry-run` switches for isolated testing.
"""

import argparse
import asyncio
import logging
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from src.ingestion.clients.weather_client import OpenMeteoClient
from src.ingestion.config.hubs import DISTRIBUTION_HUBS
from src.ingestion.models.multimodal import CompetitorPriceRecord
from src.ingestion.parsers.tabular_inventory import parse_tabular_inventory_file
from src.ingestion.repositories.bronze_competitor_repo import BronzeCompetitorPriceRepository
from src.ingestion.repositories.bronze_inventory_repo import BronzePartnerInventoryRepository
from src.ingestion.repositories.bronze_weather_repo import BronzeWeatherRepository
from src.ingestion.scrapers.competitor_scraper import CompetitorPriceScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("aura.ingestion.multimodal")

# Sample synthetic competitor URLs / mock endpoints for demonstration/testing
DEFAULT_COMPETITOR_URLS: list[str] = [
    "https://ecommerce.example.com/red-bull-energy-drink-250ml",
    "https://ecommerce.example.com/monster-energy-green-473ml",
]


def run_weather_ingestion(
    start_date: date | None = None,
    end_date: date | None = None,
    dry_run: bool = False,
) -> int:
    """Execute Open-Meteo weather metrics collection and Bronze landing.

    Args:
        start_date: Start date of observation period.
        end_date: End date of observation period.
        dry_run: When True, fetches data without persisting to Snowflake.

    Returns:
        int: Number of records processed.
    """
    logger.info("Initiating Open-Meteo weather ingestion across %d hubs...", len(DISTRIBUTION_HUBS))
    client = OpenMeteoClient()
    records = client.fetch_all_hubs_weather(start_date=start_date, end_date=end_date)
    logger.info("Collected %d weather records from Open-Meteo", len(records))

    if dry_run:
        logger.info("[DRY-RUN] Skipped Snowflake insert for %d weather records", len(records))
        return len(records)

    with BronzeWeatherRepository() as repo:
        batch = [(r.city_hub, r.state, r) for r in records]
        inserted = repo.batch_insert_weather_records(batch)
        logger.info("Successfully persisted %d weather records to Bronze", inserted)
        return inserted


async def run_competitor_ingestion(
    urls: Sequence[str] | None = None,
    dry_run: bool = False,
    mock_records: list[CompetitorPriceRecord] | None = None,
) -> int:
    """Execute competitor price scraping and Bronze landing.

    Args:
        urls: Target URLs to scrape.
        dry_run: When True, bypasses Snowflake persistence.
        mock_records: Optional pre-parsed records for offline execution.

    Returns:
        int: Number of records processed.
    """
    target_urls = urls or DEFAULT_COMPETITOR_URLS
    logger.info("Initiating competitor scraper for %d target URLs...", len(target_urls))

    if mock_records is not None:
        records = mock_records
    else:
        async with CompetitorPriceScraper() as scraper:
            records = await scraper.scrape_urls(target_urls)

    logger.info("Extracted %d competitor pricing records", len(records))

    if dry_run:
        logger.info("[DRY-RUN] Skipped Snowflake insert for %d competitor records", len(records))
        return len(records)

    with BronzeCompetitorPriceRepository() as repo:
        batch = [(r.source_url, r.competitor_brand, r) for r in records]
        inserted = repo.batch_insert_price_records(batch)
        logger.info("Successfully persisted %d competitor records to Bronze", inserted)
        return inserted


def run_inventory_ingestion(
    inventory_dir: Path | str = "data/raw/partners",
    dry_run: bool = False,
) -> int:
    """Execute legacy tabular inventory file ingestion and Bronze landing.

    Args:
        inventory_dir: Directory containing CSV/TXT inventory extracts.
        dry_run: When True, bypasses Snowflake persistence.

    Returns:
        int: Number of records processed.
    """
    target_dir = Path(inventory_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    tabular_files = sorted(
        [p for p in target_dir.iterdir() if p.suffix.lower() in (".csv", ".txt", ".tsv")]
    )

    if not tabular_files:
        logger.warning("No tabular inventory files found in %s", target_dir)
        return 0

    logger.info("Discovered %d tabular inventory file(s) in %s", len(tabular_files), target_dir)
    total_records = 0

    repo = None if dry_run else BronzePartnerInventoryRepository()

    for file_path in tabular_files:
        logger.info("Parsing inventory extract: %s", file_path.name)
        result = parse_tabular_inventory_file(file_path)

        if not result.records:
            logger.warning(
                "File %s yielded 0 valid records (%d errors)",
                file_path.name,
                len(result.errors),
            )
            continue

        logger.info(
            "Parsed %d valid records from %s (MD5: %s, delim: '%s')",
            len(result.records),
            file_path.name,
            result.file_hash_md5[:8],
            result.delimiter,
        )

        if dry_run or repo is None:
            logger.info(
                "[DRY-RUN] Ready to insert %d records for file %s",
                len(result.records),
                file_path.name,
            )
            total_records += len(result.records)
        else:
            batch = [
                (file_path.name, rec.partner_id, result.file_hash_md5, rec)
                for rec in result.records
            ]
            inserted = repo.batch_insert_inventory_records(batch)
            total_records += inserted

    return total_records


def run_multimodal_pipeline(
    source: str = "all",
    dry_run: bool = False,
    inventory_dir: str = "data/raw/partners",
    start_date: str | None = None,
    end_date: str | None = None,
) -> int:
    """Execute the multimodal ingestion pipeline orchestrator.

    Args:
        source: Ingestion source selection ('all', 'weather', 'competitor', 'inventory').
        dry_run: If True, validates data without inserting to Snowflake.
        inventory_dir: Directory containing inventory files.
        start_date: Optional start date string for weather.
        end_date: Optional end date string for weather.

    Returns:
        int: Exit status code (0 for success).
    """
    logger.info(
        "Starting multimodal ingestion pipeline [source=%s, dry_run=%s]",
        source,
        dry_run,
    )

    selected = source.lower().strip()

    if selected in ("all", "weather"):
        parsed_start = date.fromisoformat(start_date) if start_date else None
        parsed_end = date.fromisoformat(end_date) if end_date else None
        run_weather_ingestion(start_date=parsed_start, end_date=parsed_end, dry_run=dry_run)

    if selected in ("all", "competitor"):
        asyncio.run(run_competitor_ingestion(dry_run=dry_run))

    if selected in ("all", "inventory"):
        run_inventory_ingestion(inventory_dir=inventory_dir, dry_run=dry_run)

    logger.info("Multimodal ingestion pipeline completed successfully.")
    return 0


def parse_args(args: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Aura Intelligence Hub - Multimodal Ingestion Pipeline CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--source",
        choices=["all", "weather", "competitor", "inventory"],
        default="all",
        help="Specific ingestion source to execute.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Validate and parse data without writing to Snowflake Bronze tables.",
    )
    parser.add_argument(
        "--inventory-dir",
        type=str,
        default="data/raw/partners",
        help="Path to directory containing legacy inventory extracts.",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Start date for climatic observation interval (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="End date for climatic observation interval (YYYY-MM-DD).",
    )
    return parser.parse_args(args)


def main() -> None:
    """CLI script entrypoint."""
    parsed = parse_args()
    status = run_multimodal_pipeline(
        source=parsed.source,
        dry_run=parsed.dry_run,
        inventory_dir=parsed.inventory_dir,
        start_date=parsed.start_date,
        end_date=parsed.end_date,
    )
    sys.exit(status)


if __name__ == "__main__":
    main()
