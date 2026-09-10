"""Ingestion repositories module for Snowflake Bronze layer."""

from src.ingestion.repositories.bronze_competitor_repo import (
    BronzeCompetitorPriceRepository,
    get_competitor_insert_sql,
)
from src.ingestion.repositories.bronze_inventory_repo import (
    BronzePartnerInventoryRepository,
    get_inventory_insert_sql,
)
from src.ingestion.repositories.bronze_invoice_repo import (
    BronzeInvoiceRepository,
    get_insert_sql,
)
from src.ingestion.repositories.bronze_weather_repo import (
    BronzeWeatherRepository,
    get_weather_insert_sql,
)

__all__ = [
    "BronzeCompetitorPriceRepository",
    "BronzeInvoiceRepository",
    "BronzePartnerInventoryRepository",
    "BronzeWeatherRepository",
    "get_competitor_insert_sql",
    "get_insert_sql",
    "get_inventory_insert_sql",
    "get_weather_insert_sql",
]
