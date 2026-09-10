"""Dagster Software-Defined Assets (SDAs) for the Medallion Lakehouse."""

from src.orchestration.assets.bronze import (
    bronze_competitor_prices_raw,
    bronze_invoices_raw,
    bronze_partner_inventory_raw,
    bronze_weather_metrics_raw,
)
from src.orchestration.assets.silver import (
    silver_competitor_prices,
    silver_invoice_items,
    silver_invoices,
    silver_partner_inventory,
    silver_weather_metrics,
)

__all__ = [
    "bronze_competitor_prices_raw",
    "bronze_invoices_raw",
    "bronze_partner_inventory_raw",
    "bronze_weather_metrics_raw",
    "silver_competitor_prices",
    "silver_invoice_items",
    "silver_invoices",
    "silver_partner_inventory",
    "silver_weather_metrics",
]
