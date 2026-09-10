"""Competitor scrapers module."""

from src.ingestion.scrapers.competitor_scraper import (
    CompetitorPriceScraper,
    detect_brand,
    extract_volume_ml,
    parse_price_brl,
)

__all__ = [
    "CompetitorPriceScraper",
    "detect_brand",
    "extract_volume_ml",
    "parse_price_brl",
]
