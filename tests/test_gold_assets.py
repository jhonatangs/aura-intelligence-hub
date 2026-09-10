"""Unit tests for Dagster Gold Software-Defined Assets (SDAs)."""

from unittest.mock import MagicMock, patch

from dagster import build_asset_context, materialize

from src.orchestration.assets.bronze import (
    bronze_competitor_prices_raw,
    bronze_invoices_raw,
    bronze_partner_inventory_raw,
    bronze_weather_metrics_raw,
)
from src.orchestration.assets.gold import (
    gold_dim_date,
    gold_dim_hubs,
    gold_dim_partners,
    gold_dim_skus,
    gold_fact_competitor_pricing,
    gold_fact_inventory_snapshot,
    gold_fact_sellout,
)
from src.orchestration.assets.silver import (
    silver_competitor_prices,
    silver_invoice_items,
    silver_invoices,
    silver_partner_inventory,
    silver_weather_metrics,
)
from src.orchestration.definitions import defs

SERVICE_PATCH_TARGET = "src.orchestration.assets.gold.GoldTransformationService"
SILVER_SERVICE_PATCH = "src.orchestration.assets.silver.SilverTransformationService"


def test_gold_dim_date_asset_execution() -> None:
    """Verify gold_dim_date asset execution and output metadata."""
    context = build_asset_context()
    mock_service = MagicMock()
    mock_service.transform_dim_date.return_value = {
        "status": "success",
        "target_table": "AURA_LAKEHOUSE.GOLD.DIM_DATE",
        "rows_affected": 1826,
    }

    with patch(SERVICE_PATCH_TARGET, return_value=mock_service):
        output = gold_dim_date(context)

    assert output.value["status"] == "success"
    assert output.metadata["schema_layer"].value == "GOLD"
    assert output.metadata["grain"].value == "One row per calendar day"
    assert output.metadata["rows_affected"].value == 1826


def test_gold_dim_partners_asset_execution() -> None:
    """Verify gold_dim_partners asset execution and output metadata."""
    context = build_asset_context()
    mock_service = MagicMock()
    mock_service.transform_dim_partners.return_value = {
        "status": "success",
        "target_table": "AURA_LAKEHOUSE.GOLD.DIM_PARTNERS",
        "rows_affected": 15,
    }

    with patch(SERVICE_PATCH_TARGET, return_value=mock_service):
        output = gold_dim_partners(
            context,
            silver_invoices={"status": "success"},
            silver_partner_inventory={"status": "success"},
        )

    assert output.value["status"] == "success"
    assert output.metadata["schema_layer"].value == "GOLD"
    assert output.metadata["rows_affected"].value == 15


def test_gold_dim_skus_asset_execution() -> None:
    """Verify gold_dim_skus asset execution and output metadata."""
    context = build_asset_context()
    mock_service = MagicMock()
    mock_service.transform_dim_skus.return_value = {
        "status": "success",
        "target_table": "AURA_LAKEHOUSE.GOLD.DIM_SKUS",
        "rows_affected": 3,
    }

    with patch(SERVICE_PATCH_TARGET, return_value=mock_service):
        output = gold_dim_skus(
            context,
            silver_invoice_items={"status": "success"},
            silver_partner_inventory={"status": "success"},
        )

    assert output.value["status"] == "success"
    assert output.metadata["schema_layer"].value == "GOLD"
    assert output.metadata["rows_affected"].value == 3


def test_gold_dim_hubs_asset_execution() -> None:
    """Verify gold_dim_hubs asset execution and output metadata."""
    context = build_asset_context()
    mock_service = MagicMock()
    mock_service.transform_dim_hubs.return_value = {
        "status": "success",
        "target_table": "AURA_LAKEHOUSE.GOLD.DIM_HUBS",
        "rows_affected": 10,
    }

    with patch(SERVICE_PATCH_TARGET, return_value=mock_service):
        output = gold_dim_hubs(
            context,
            silver_weather_metrics={"status": "success"},
        )

    assert output.value["status"] == "success"
    assert output.metadata["schema_layer"].value == "GOLD"
    assert output.metadata["rows_affected"].value == 10


def test_gold_fact_sellout_asset_execution() -> None:
    """Verify gold_fact_sellout asset execution and output metadata."""
    context = build_asset_context()
    mock_service = MagicMock()
    mock_service.transform_fact_sellout.return_value = {
        "status": "success",
        "target_table": "AURA_LAKEHOUSE.GOLD.FACT_SELLOUT",
        "rows_affected": 45,
    }

    with patch(SERVICE_PATCH_TARGET, return_value=mock_service):
        output = gold_fact_sellout(
            context,
            silver_invoices={"status": "success"},
            silver_invoice_items={"status": "success"},
            gold_dim_date={"status": "success"},
            gold_dim_partners={"status": "success"},
            gold_dim_skus={"status": "success"},
        )

    assert output.value["status"] == "success"
    assert output.metadata["schema_layer"].value == "GOLD"
    assert output.metadata["rows_affected"].value == 45


def test_gold_fact_inventory_snapshot_asset_execution() -> None:
    """Verify gold_fact_inventory_snapshot asset execution and output metadata."""
    context = build_asset_context()
    mock_service = MagicMock()
    mock_service.transform_fact_inventory_snapshot.return_value = {
        "status": "success",
        "target_table": "AURA_LAKEHOUSE.GOLD.FACT_INVENTORY_SNAPSHOT",
        "rows_affected": 30,
    }

    with patch(SERVICE_PATCH_TARGET, return_value=mock_service):
        output = gold_fact_inventory_snapshot(
            context,
            silver_partner_inventory={"status": "success"},
            gold_dim_date={"status": "success"},
            gold_dim_partners={"status": "success"},
            gold_dim_skus={"status": "success"},
        )

    assert output.value["status"] == "success"
    assert output.metadata["schema_layer"].value == "GOLD"
    assert output.metadata["rows_affected"].value == 30


def test_gold_fact_competitor_pricing_asset_execution() -> None:
    """Verify gold_fact_competitor_pricing asset execution and output metadata."""
    context = build_asset_context()
    mock_service = MagicMock()
    mock_service.transform_fact_competitor_pricing.return_value = {
        "status": "success",
        "target_table": "AURA_LAKEHOUSE.GOLD.FACT_COMPETITOR_PRICING",
        "rows_affected": 20,
    }

    with patch(SERVICE_PATCH_TARGET, return_value=mock_service):
        output = gold_fact_competitor_pricing(
            context,
            silver_competitor_prices={"status": "success"},
            gold_dim_date={"status": "success"},
        )

    assert output.value["status"] == "success"
    assert output.metadata["schema_layer"].value == "GOLD"
    assert output.metadata["rows_affected"].value == 20


def test_materialize_end_to_end_lakehouse_with_gold() -> None:
    """Verify full end-to-end DAG materialization across Bronze, Silver, and Gold."""
    mock_res = {"status": "success", "rows_affected": 1}
    mock_silver_svc = MagicMock()
    mock_silver_svc.transform_invoices_header.return_value = mock_res
    mock_silver_svc.transform_invoice_items.return_value = mock_res
    mock_silver_svc.transform_competitor_prices.return_value = mock_res
    mock_silver_svc.transform_weather_metrics.return_value = mock_res
    mock_silver_svc.transform_partner_inventory.return_value = mock_res

    mock_gold_svc = MagicMock()
    mock_gold_svc.transform_dim_date.return_value = mock_res
    mock_gold_svc.transform_dim_partners.return_value = mock_res
    mock_gold_svc.transform_dim_skus.return_value = mock_res
    mock_gold_svc.transform_dim_hubs.return_value = mock_res
    mock_gold_svc.transform_fact_sellout.return_value = mock_res
    mock_gold_svc.transform_fact_inventory_snapshot.return_value = mock_res
    mock_gold_svc.transform_fact_competitor_pricing.return_value = mock_res

    with (
        patch(SILVER_SERVICE_PATCH, return_value=mock_silver_svc),
        patch(SERVICE_PATCH_TARGET, return_value=mock_gold_svc),
    ):
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
                gold_dim_date,
                gold_dim_partners,
                gold_dim_skus,
                gold_dim_hubs,
                gold_fact_sellout,
                gold_fact_inventory_snapshot,
                gold_fact_competitor_pricing,
            ]
        )
    assert result.success


def test_dagster_definitions_registry_with_gold() -> None:
    """Verify Dagster Definitions contains all Bronze, Silver, and Gold assets."""
    keys = {key.path[-1] for key in defs.resolve_all_asset_keys()}

    expected_gold = {
        "gold_dim_date",
        "gold_dim_partners",
        "gold_dim_skus",
        "gold_dim_hubs",
        "gold_fact_sellout",
        "gold_fact_inventory_snapshot",
        "gold_fact_competitor_pricing",
    }
    for asset_key in expected_gold:
        assert asset_key in keys
