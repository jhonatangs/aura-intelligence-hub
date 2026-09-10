"""Domain data contracts and validation models."""

from src.ingestion.models.invoice import (
    InvoiceItem,
    InvoiceMetadata,
    RawInvoicePayload,
    validate_cnpj,
)
from src.ingestion.models.multimodal import (
    CompetitorPriceRecord,
    PartnerInventoryRecord,
    WeatherMetricRecord,
)

__all__ = [
    "CompetitorPriceRecord",
    "InvoiceItem",
    "InvoiceMetadata",
    "PartnerInventoryRecord",
    "RawInvoicePayload",
    "WeatherMetricRecord",
    "validate_cnpj",
]
