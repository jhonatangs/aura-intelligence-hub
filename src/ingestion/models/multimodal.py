"""Multimodal ingestion data contracts and Pydantic v2 validation models.

Defines domain contracts for competitor price scrapers, Open-Meteo weather
metric feeds, and legacy partner warehouse inventory files.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CompetitorPriceRecord(BaseModel):
    """Competitor price intelligence record scraped from digital retail channels.

    Attributes:
        competitor_brand: Target competitor brand ('RED_BULL' or 'MONSTER').
        product_title: Full consumer-facing product title.
        volume_ml: Beverage container volume in milliliters.
        price_brl: Normalized retail price in Brazilian Reais (BRL).
        stock_status: Availability status ('IN_STOCK', 'OUT_OF_STOCK', 'UNKNOWN').
        timestamp: Observation or scraping timestamp.
        source_url: Source URL where the price was observed.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    competitor_brand: Literal["RED_BULL", "MONSTER"]
    product_title: str = Field(min_length=1, max_length=255)
    volume_ml: int = Field(gt=0, description="Volume in milliliters")
    price_brl: float = Field(gt=0.0, description="Retail price in BRL")
    stock_status: Literal["IN_STOCK", "OUT_OF_STOCK", "UNKNOWN"] = "IN_STOCK"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source_url: str = Field(default="", max_length=500)

    @field_validator("competitor_brand", mode="before")
    @classmethod
    def normalize_brand(cls, value: str) -> str:
        """Normalize brand string to uppercase standard token."""
        normalized = value.strip().upper().replace(" ", "_").replace("-", "_")
        if normalized in ("RED_BULL", "REDBULL"):
            return "RED_BULL"
        if normalized in ("MONSTER", "MONSTER_ENERGY"):
            return "MONSTER"
        return normalized

    @field_validator("stock_status", mode="before")
    @classmethod
    def normalize_stock_status(cls, value: str | bool) -> str:
        """Normalize stock status into standardized string literal."""
        if isinstance(value, bool):
            return "IN_STOCK" if value else "OUT_OF_STOCK"
        val = str(value).strip().upper()
        if val in ("IN_STOCK", "AVAILABLE", "TRUE", "1", "EM_ESTOQUE"):
            return "IN_STOCK"
        if val in ("OUT_OF_STOCK", "UNAVAILABLE", "FALSE", "0", "ESGOTADO"):
            return "OUT_OF_STOCK"
        return "UNKNOWN"


class WeatherMetricRecord(BaseModel):
    """Climatic metric observation record ingested from Open-Meteo REST API.

    Attributes:
        city_hub: Distribution center or metropolitan hub name.
        state: Two-letter Brazilian state abbreviation.
        date: Observation date.
        temp_max: Maximum daily temperature in degrees Celsius.
        temp_min: Minimum daily temperature in degrees Celsius.
        precipitation_sum: Total daily precipitation in millimeters.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    city_hub: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=2, max_length=10)
    date: date
    temp_max: float = Field(description="Maximum temperature in Celsius")
    temp_min: float = Field(description="Minimum temperature in Celsius")
    precipitation_sum: float = Field(ge=0.0, description="Daily precipitation sum in mm")

    @field_validator("state", mode="before")
    @classmethod
    def normalize_state(cls, value: str) -> str:
        """Normalize state code to uppercase."""
        return value.strip().upper()

    @model_validator(mode="after")
    def validate_temperatures(self) -> "WeatherMetricRecord":
        """Assert maximum temperature is greater than or equal to minimum temperature."""
        if self.temp_max < self.temp_min:
            raise ValueError(
                f"temp_max ({self.temp_max}) cannot be lower than temp_min ({self.temp_min})"
            )
        return self


class PartnerInventoryRecord(BaseModel):
    """Inventory balance snapshot record from legacy partner warehouse systems.

    Attributes:
        partner_id: Partner distributor unique identifier.
        sku: Stock Keeping Unit identifier (e.g., AURA_250ML, AURA_TROPICAL_473ML).
        batch_id: Production lot or batch identifier.
        stock_quantity: Physical inventory balance count.
        warehouse_location: Warehouse shelf, bay, or site identifier.
        snapshot_date: Date of the inventory balance snapshot.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    partner_id: str = Field(min_length=1, max_length=100)
    sku: str = Field(min_length=1, max_length=100)
    batch_id: str = Field(min_length=1, max_length=100)
    stock_quantity: int = Field(ge=0, description="Quantity in inventory (non-negative)")
    warehouse_location: str = Field(min_length=1, max_length=100)
    snapshot_date: date

    @field_validator("partner_id", "sku", "batch_id", "warehouse_location", mode="before")
    @classmethod
    def clean_identifier(cls, value: str) -> str:
        """Strip and validate identifier strings."""
        val = str(value).strip()
        if not val:
            raise ValueError("Identifier fields cannot be empty")
        return val
