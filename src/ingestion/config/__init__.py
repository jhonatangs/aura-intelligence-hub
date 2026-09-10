"""Configuration module for ingestion components."""

from src.ingestion.config.hubs import (
    DISTRIBUTION_HUBS,
    DistributionHub,
    get_all_hubs,
    get_hub_by_id,
)

__all__ = [
    "DISTRIBUTION_HUBS",
    "DistributionHub",
    "get_all_hubs",
    "get_hub_by_id",
]
