"""Dagster Software-Defined Assets (SDAs) for Snowflake Silver layer.

Declares assets for cleansed, normalized, and deduplicated Silver tables
with upstream dependencies on Bronze raw landing assets.
"""

from typing import Any

from dagster import (
    AssetExecutionContext,
    MetadataValue,
    Output,
    asset,
)

from src.transformation.services.silver_service import SilverTransformationService


@asset(
    group_name="silver",
    description="Normalized and deduplicated partner invoice headers in Snowflake Silver layer.",
    compute_kind="snowflake",
)
def silver_invoices(
    context: AssetExecutionContext,
    bronze_invoices_raw: dict[str, Any],
) -> Output[dict[str, Any]]:
    """Materialize conformed B2B partner invoices into Snowflake Silver layer."""
    context.log.info("Materializing asset: silver_invoices")
    service = SilverTransformationService()
    result = service.transform_invoices_header()
    return Output(
        value=result,
        metadata={
            "target_table": MetadataValue.text(result.get("target_table", "")),
            "schema_layer": MetadataValue.text("SILVER"),
            "grain": MetadataValue.text("One row per invoice_number and partner_id"),
            "upstream_asset": MetadataValue.text("bronze_invoices_raw"),
            "rows_affected": MetadataValue.int(result.get("rows_affected", 0)),
        },
    )


@asset(
    group_name="silver",
    description="Normalized and flattened partner invoice line items in Snowflake Silver layer.",
    compute_kind="snowflake",
)
def silver_invoice_items(
    context: AssetExecutionContext,
    bronze_invoices_raw: dict[str, Any],
) -> Output[dict[str, Any]]:
    """Materialize conformed invoice line items into Snowflake Silver layer."""
    context.log.info("Materializing asset: silver_invoice_items")
    service = SilverTransformationService()
    result = service.transform_invoice_items()
    return Output(
        value=result,
        metadata={
            "target_table": MetadataValue.text(result.get("target_table", "")),
            "schema_layer": MetadataValue.text("SILVER"),
            "grain": MetadataValue.text("One row per invoice line item"),
            "upstream_asset": MetadataValue.text("bronze_invoices_raw"),
            "rows_affected": MetadataValue.int(result.get("rows_affected", 0)),
        },
    )


@asset(
    group_name="silver",
    description="Cleansed competitor price observations in Snowflake Silver layer.",
    compute_kind="snowflake",
)
def silver_competitor_prices(
    context: AssetExecutionContext,
    bronze_competitor_prices_raw: dict[str, Any],
) -> Output[dict[str, Any]]:
    """Materialize conformed competitor price observations into Snowflake Silver layer."""
    context.log.info("Materializing asset: silver_competitor_prices")
    service = SilverTransformationService()
    result = service.transform_competitor_prices()
    return Output(
        value=result,
        metadata={
            "target_table": MetadataValue.text(result.get("target_table", "")),
            "schema_layer": MetadataValue.text("SILVER"),
            "competitors": MetadataValue.text("RED_BULL, MONSTER"),
            "upstream_asset": MetadataValue.text("bronze_competitor_prices_raw"),
            "rows_affected": MetadataValue.int(result.get("rows_affected", 0)),
        },
    )


@asset(
    group_name="silver",
    description="Normalized daily weather and temperature observations per distribution hub.",
    compute_kind="snowflake",
)
def silver_weather_metrics(
    context: AssetExecutionContext,
    bronze_weather_metrics_raw: dict[str, Any],
) -> Output[dict[str, Any]]:
    """Materialize conformed macro climatic metrics into Snowflake Silver layer."""
    context.log.info("Materializing asset: silver_weather_metrics")
    service = SilverTransformationService()
    result = service.transform_weather_metrics()
    return Output(
        value=result,
        metadata={
            "target_table": MetadataValue.text(result.get("target_table", "")),
            "schema_layer": MetadataValue.text("SILVER"),
            "upstream_asset": MetadataValue.text("bronze_weather_metrics_raw"),
            "rows_affected": MetadataValue.int(result.get("rows_affected", 0)),
        },
    )


@asset(
    group_name="silver",
    description="Cleansed and deduplicated partner warehouse inventory balances.",
    compute_kind="snowflake",
)
def silver_partner_inventory(
    context: AssetExecutionContext,
    bronze_partner_inventory_raw: dict[str, Any],
) -> Output[dict[str, Any]]:
    """Materialize conformed partner warehouse inventory balances into Snowflake Silver layer."""
    context.log.info("Materializing asset: silver_partner_inventory")
    service = SilverTransformationService()
    result = service.transform_partner_inventory()
    return Output(
        value=result,
        metadata={
            "target_table": MetadataValue.text(result.get("target_table", "")),
            "schema_layer": MetadataValue.text("SILVER"),
            "upstream_asset": MetadataValue.text("bronze_partner_inventory_raw"),
            "rows_affected": MetadataValue.int(result.get("rows_affected", 0)),
        },
    )
