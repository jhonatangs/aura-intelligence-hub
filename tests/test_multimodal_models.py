"""Unit tests for multimodal Pydantic domain models and validation contracts."""

from datetime import date

import pytest
from pydantic import ValidationError

from src.ingestion.models.multimodal import (
    CompetitorPriceRecord,
    PartnerInventoryRecord,
    WeatherMetricRecord,
)


class TestCompetitorPriceRecordValidation:
    """Validation test suite for CompetitorPriceRecord."""

    def test_valid_competitor_records(self) -> None:
        """Verify valid record instantiation for Red Bull and Monster."""
        rec1 = CompetitorPriceRecord(
            competitor_brand="RED_BULL",
            product_title="Red Bull Energy Drink 250ml",
            volume_ml=250,
            price_brl=9.99,
            stock_status="IN_STOCK",
        )
        assert rec1.competitor_brand == "RED_BULL"
        assert rec1.volume_ml == 250
        assert rec1.price_brl == 9.99
        assert rec1.stock_status == "IN_STOCK"

        rec2 = CompetitorPriceRecord(
            competitor_brand="monster energy",  # tests brand normalization
            product_title="Monster Energy 473ml",
            volume_ml=473,
            price_brl=11.50,
            stock_status="esgotado",  # tests stock status normalization
        )
        assert rec2.competitor_brand == "MONSTER"
        assert rec2.stock_status == "OUT_OF_STOCK"

    def test_non_positive_price_rejected(self) -> None:
        """Verify negative or zero prices are rejected."""
        with pytest.raises(ValidationError):
            CompetitorPriceRecord(
                competitor_brand="RED_BULL",
                product_title="Red Bull 250ml",
                volume_ml=250,
                price_brl=0.0,
            )
        with pytest.raises(ValidationError):
            CompetitorPriceRecord(
                competitor_brand="RED_BULL",
                product_title="Red Bull 250ml",
                volume_ml=250,
                price_brl=-5.0,
            )

    def test_non_positive_volume_rejected(self) -> None:
        """Verify zero or negative container volume is rejected."""
        with pytest.raises(ValidationError):
            CompetitorPriceRecord(
                competitor_brand="RED_BULL",
                product_title="Red Bull 250ml",
                volume_ml=0,
                price_brl=10.0,
            )


class TestWeatherMetricRecordValidation:
    """Validation test suite for WeatherMetricRecord."""

    def test_valid_weather_record(self) -> None:
        """Verify valid weather record instantiation."""
        rec = WeatherMetricRecord(
            city_hub="São Paulo",
            state="sp",  # tests uppercase normalization
            date=date(2026, 3, 10),
            temp_max=30.5,
            temp_min=20.0,
            precipitation_sum=0.0,
        )
        assert rec.state == "SP"
        assert rec.temp_max == 30.5
        assert rec.temp_min == 20.0

    def test_temp_max_lower_than_min_rejected(self) -> None:
        """Verify ValueError is raised if temp_max is less than temp_min."""
        with pytest.raises(ValidationError, match="cannot be lower than temp_min"):
            WeatherMetricRecord(
                city_hub="São Paulo",
                state="SP",
                date=date(2026, 3, 10),
                temp_max=18.0,
                temp_min=25.0,
                precipitation_sum=0.0,
            )

    def test_negative_precipitation_rejected(self) -> None:
        """Verify negative precipitation sum is rejected."""
        with pytest.raises(ValidationError):
            WeatherMetricRecord(
                city_hub="Curitiba",
                state="PR",
                date=date(2026, 3, 10),
                temp_max=22.0,
                temp_min=14.0,
                precipitation_sum=-1.5,
            )


class TestPartnerInventoryRecordValidation:
    """Validation test suite for PartnerInventoryRecord."""

    def test_valid_partner_inventory_record(self) -> None:
        """Verify valid inventory balance record instantiation."""
        rec = PartnerInventoryRecord(
            partner_id="PARTNER_SP_01",
            sku="AURA_250ML",
            batch_id="BATCH-001",
            stock_quantity=1500,
            warehouse_location="WH_SP_MAIN",
            snapshot_date=date(2026, 3, 1),
        )
        assert rec.partner_id == "PARTNER_SP_01"
        assert rec.stock_quantity == 1500

    def test_negative_stock_quantity_rejected(self) -> None:
        """Verify negative stock quantities are rejected."""
        with pytest.raises(ValidationError):
            PartnerInventoryRecord(
                partner_id="PARTNER_SP_01",
                sku="AURA_250ML",
                batch_id="BATCH-001",
                stock_quantity=-10,
                warehouse_location="WH_SP_MAIN",
                snapshot_date=date(2026, 3, 1),
            )

    def test_empty_identifiers_rejected(self) -> None:
        """Verify empty string identifiers are rejected."""
        with pytest.raises(ValidationError):
            PartnerInventoryRecord(
                partner_id="   ",
                sku="AURA_250ML",
                batch_id="BATCH-001",
                stock_quantity=100,
                warehouse_location="WH-1",
                snapshot_date=date(2026, 3, 1),
            )
