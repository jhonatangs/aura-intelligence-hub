"""Unit tests for Dagster Bronze Software-Defined Assets (SDAs)."""

from dagster import build_asset_context, materialize

from src.orchestration.assets.bronze import (
    bronze_competitor_prices_raw,
    bronze_invoices_raw,
    bronze_partner_inventory_raw,
    bronze_weather_metrics_raw,
)
from src.orchestration.definitions import defs


def test_bronze_invoices_asset_execution() -> None:
    """Verify bronze_invoices_raw asset execution and output metadata."""
    context = build_asset_context()
    output = bronze_invoices_raw(context)

    assert output.value["status"] == "success"
    assert output.value["target_table"] == "AURA_LAKEHOUSE.BRONZE.INVOICES_RAW"
    assert "target_table" in output.metadata
    assert output.metadata["schema_layer"].value == "BRONZE"


def test_bronze_weather_asset_execution() -> None:
    """Verify bronze_weather_metrics_raw asset execution and output metadata."""
    context = build_asset_context()
    output = bronze_weather_metrics_raw(context)

    assert output.value["status"] == "success"
    assert output.value["target_table"] == "AURA_LAKEHOUSE.BRONZE.WEATHER_METRICS_RAW"
    assert output.metadata["schema_layer"].value == "BRONZE"
    assert output.metadata["hubs_count"].value == 10


def test_bronze_competitor_asset_execution() -> None:
    """Verify bronze_competitor_prices_raw asset execution and output metadata."""
    context = build_asset_context()
    output = bronze_competitor_prices_raw(context)

    assert output.value["status"] == "success"
    assert output.value["target_table"] == "AURA_LAKEHOUSE.BRONZE.COMPETITOR_PRICES_RAW"
    assert "RED_BULL" in output.metadata["competitors"].value


def test_bronze_partner_inventory_asset_execution() -> None:
    """Verify bronze_partner_inventory_raw asset execution and output metadata."""
    context = build_asset_context()
    output = bronze_partner_inventory_raw(context)

    assert output.value["status"] == "success"
    assert output.value["target_table"] == "AURA_LAKEHOUSE.BRONZE.PARTNER_INVENTORY_RAW"
    assert output.metadata["hash_algorithm"].value == "MD5"


def test_materialize_all_bronze_assets() -> None:
    """Verify materialization of full bronze asset graph via Dagster materialize API."""
    result = materialize(
        [
            bronze_invoices_raw,
            bronze_weather_metrics_raw,
            bronze_competitor_prices_raw,
            bronze_partner_inventory_raw,
        ]
    )
    assert result.success


def test_dagster_definitions_registry() -> None:
    """Verify defs contains all 4 bronze assets properly registered."""
    keys = {key.path[-1] for key in defs.resolve_all_asset_keys()}
    assert "bronze_invoices_raw" in keys
    assert "bronze_weather_metrics_raw" in keys
    assert "bronze_competitor_prices_raw" in keys
    assert "bronze_partner_inventory_raw" in keys
