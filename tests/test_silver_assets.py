"""Unit tests for Dagster Silver Software-Defined Assets (SDAs)."""

from unittest.mock import MagicMock, patch

from dagster import build_asset_context, materialize

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
from src.orchestration.definitions import defs

SERVICE_PATCH_TARGET = "src.orchestration.assets.silver.SilverTransformationService"


def test_silver_invoices_asset_execution() -> None:
    """Verify silver_invoices asset execution and output metadata."""
    context = build_asset_context()
    mock_service = MagicMock()
    mock_service.transform_invoices_header.return_value = {
        "status": "success",
        "target_table": "AURA_LAKEHOUSE.SILVER.INVOICES",
        "rows_affected": 12,
    }

    with patch(SERVICE_PATCH_TARGET, return_value=mock_service):
        output = silver_invoices(context, bronze_invoices_raw={"status": "success"})

    assert output.value["status"] == "success"
    assert output.metadata["schema_layer"].value == "SILVER"
    assert output.metadata["upstream_asset"].value == "bronze_invoices_raw"
    assert output.metadata["rows_affected"].value == 12


def test_silver_invoice_items_asset_execution() -> None:
    """Verify silver_invoice_items asset execution and output metadata."""
    context = build_asset_context()
    mock_service = MagicMock()
    mock_service.transform_invoice_items.return_value = {
        "status": "success",
        "target_table": "AURA_LAKEHOUSE.SILVER.INVOICE_ITEMS",
        "rows_affected": 36,
    }

    with patch(SERVICE_PATCH_TARGET, return_value=mock_service):
        output = silver_invoice_items(context, bronze_invoices_raw={"status": "success"})

    assert output.value["status"] == "success"
    assert output.metadata["schema_layer"].value == "SILVER"
    assert output.metadata["upstream_asset"].value == "bronze_invoices_raw"
    assert output.metadata["rows_affected"].value == 36


def test_silver_competitor_prices_asset_execution() -> None:
    """Verify silver_competitor_prices asset execution and output metadata."""
    context = build_asset_context()
    mock_service = MagicMock()
    mock_service.transform_competitor_prices.return_value = {
        "status": "success",
        "target_table": "AURA_LAKEHOUSE.SILVER.COMPETITOR_PRICES",
        "rows_affected": 8,
    }

    with patch(SERVICE_PATCH_TARGET, return_value=mock_service):
        output = silver_competitor_prices(
            context,
            bronze_competitor_prices_raw={"status": "success"},
        )

    assert output.value["status"] == "success"
    assert output.metadata["schema_layer"].value == "SILVER"
    assert output.metadata["upstream_asset"].value == "bronze_competitor_prices_raw"
    assert "RED_BULL" in output.metadata["competitors"].value


def test_silver_weather_metrics_asset_execution() -> None:
    """Verify silver_weather_metrics asset execution and output metadata."""
    context = build_asset_context()
    mock_service = MagicMock()
    mock_service.transform_weather_metrics.return_value = {
        "status": "success",
        "target_table": "AURA_LAKEHOUSE.SILVER.WEATHER_METRICS",
        "rows_affected": 30,
    }

    with patch(SERVICE_PATCH_TARGET, return_value=mock_service):
        output = silver_weather_metrics(
            context,
            bronze_weather_metrics_raw={"status": "success"},
        )

    assert output.value["status"] == "success"
    assert output.metadata["schema_layer"].value == "SILVER"
    assert output.metadata["upstream_asset"].value == "bronze_weather_metrics_raw"


def test_silver_partner_inventory_asset_execution() -> None:
    """Verify silver_partner_inventory asset execution and output metadata."""
    context = build_asset_context()
    mock_service = MagicMock()
    mock_service.transform_partner_inventory.return_value = {
        "status": "success",
        "target_table": "AURA_LAKEHOUSE.SILVER.PARTNER_INVENTORY",
        "rows_affected": 50,
    }

    with patch(SERVICE_PATCH_TARGET, return_value=mock_service):
        output = silver_partner_inventory(
            context,
            bronze_partner_inventory_raw={"status": "success"},
        )

    assert output.value["status"] == "success"
    assert output.metadata["schema_layer"].value == "SILVER"
    assert output.metadata["upstream_asset"].value == "bronze_partner_inventory_raw"


def test_materialize_end_to_end_lakehouse_graph() -> None:
    """Verify end-to-end DAG materialization across Bronze and Silver layers."""
    mock_service = MagicMock()
    mock_service.transform_invoices_header.return_value = {
        "status": "success",
        "target_table": "AURA_LAKEHOUSE.SILVER.INVOICES",
        "rows_affected": 1,
    }
    mock_service.transform_invoice_items.return_value = {
        "status": "success",
        "target_table": "AURA_LAKEHOUSE.SILVER.INVOICE_ITEMS",
        "rows_affected": 1,
    }
    mock_service.transform_competitor_prices.return_value = {
        "status": "success",
        "target_table": "AURA_LAKEHOUSE.SILVER.COMPETITOR_PRICES",
        "rows_affected": 1,
    }
    mock_service.transform_weather_metrics.return_value = {
        "status": "success",
        "target_table": "AURA_LAKEHOUSE.SILVER.WEATHER_METRICS",
        "rows_affected": 1,
    }
    mock_service.transform_partner_inventory.return_value = {
        "status": "success",
        "target_table": "AURA_LAKEHOUSE.SILVER.PARTNER_INVENTORY",
        "rows_affected": 1,
    }

    with patch(SERVICE_PATCH_TARGET, return_value=mock_service):
        result = materialize(
            [
                bronze_invoices_raw,
                bronze_weather_metrics_raw,
                bronze_competitor_prices_raw,
                bronze_partner_inventory_raw,
                silver_invoices,
                silver_invoice_items,
                silver_competitor_prices,
                silver_weather_metrics,
                silver_partner_inventory,
            ]
        )
    assert result.success


def test_dagster_definitions_registry_with_silver() -> None:
    """Verify Dagster Definitions contains all 4 bronze and 5 silver assets."""
    keys = {key.path[-1] for key in defs.resolve_all_asset_keys()}

    expected_assets = {
        "bronze_invoices_raw",
        "bronze_weather_metrics_raw",
        "bronze_competitor_prices_raw",
        "bronze_partner_inventory_raw",
        "silver_invoices",
        "silver_invoice_items",
        "silver_competitor_prices",
        "silver_weather_metrics",
        "silver_partner_inventory",
    }
    for asset_key in expected_assets:
        assert asset_key in keys
