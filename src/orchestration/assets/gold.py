"""Dagster Software-Defined Assets (SDAs) for Snowflake Gold layer.

Declares dimensional star-schema assets for curated dimensions and facts with
upstream lineage linking Silver conformed models and Gold dimensional entities.
"""

from typing import Any

from dagster import (
    AssetExecutionContext,
    MetadataValue,
    Output,
    asset,
)

from src.transformation.services.gold_service import GoldTransformationService

# -----------------------------------------------------------------------------
# Gold Dimensions
# -----------------------------------------------------------------------------


@asset(
    group_name="gold",
    description="Deterministic calendar date dimension for temporal analytics.",
    compute_kind="snowflake",
)
def gold_dim_date(
    context: AssetExecutionContext,
) -> Output[dict[str, Any]]:
    """Materialize calendar date dimension in Snowflake Gold layer."""
    context.log.info("Materializing asset: gold_dim_date")
    service = GoldTransformationService()
    result = service.transform_dim_date()
    return Output(
        value=result,
        metadata={
            "target_table": MetadataValue.text(result.get("target_table", "")),
            "schema_layer": MetadataValue.text("GOLD"),
            "grain": MetadataValue.text("One row per calendar day"),
            "rows_affected": MetadataValue.int(result.get("rows_affected", 0)),
        },
    )


@asset(
    group_name="gold",
    description="Conformed partner dimension extracted from invoices and inventory.",
    compute_kind="snowflake",
)
def gold_dim_partners(
    context: AssetExecutionContext,
    silver_invoices: dict[str, Any],
    silver_partner_inventory: dict[str, Any],
) -> Output[dict[str, Any]]:
    """Materialize commercial partners dimension in Snowflake Gold layer."""
    context.log.info("Materializing asset: gold_dim_partners")
    service = GoldTransformationService()
    result = service.transform_dim_partners()
    return Output(
        value=result,
        metadata={
            "target_table": MetadataValue.text(result.get("target_table", "")),
            "schema_layer": MetadataValue.text("GOLD"),
            "grain": MetadataValue.text("One row per distinct partner_id"),
            "upstream_assets": MetadataValue.text("silver_invoices, silver_partner_inventory"),
            "rows_affected": MetadataValue.int(result.get("rows_affected", 0)),
        },
    )


@asset(
    group_name="gold",
    description="Conformed product SKU dimension mapping volume, flavor, and packaging.",
    compute_kind="snowflake",
)
def gold_dim_skus(
    context: AssetExecutionContext,
    silver_invoice_items: dict[str, Any],
    silver_partner_inventory: dict[str, Any],
) -> Output[dict[str, Any]]:
    """Materialize product SKU dimension in Snowflake Gold layer."""
    context.log.info("Materializing asset: gold_dim_skus")
    service = GoldTransformationService()
    result = service.transform_dim_skus()
    return Output(
        value=result,
        metadata={
            "target_table": MetadataValue.text(result.get("target_table", "")),
            "schema_layer": MetadataValue.text("GOLD"),
            "grain": MetadataValue.text("One row per product SKU"),
            "upstream_assets": MetadataValue.text("silver_invoice_items, silver_partner_inventory"),
            "rows_affected": MetadataValue.int(result.get("rows_affected", 0)),
        },
    )


@asset(
    group_name="gold",
    description="Logistics distribution hubs dimension with coordinates and timezones.",
    compute_kind="snowflake",
)
def gold_dim_hubs(
    context: AssetExecutionContext,
    silver_weather_metrics: dict[str, Any],
) -> Output[dict[str, Any]]:
    """Materialize logistics distribution hubs dimension in Snowflake Gold layer."""
    context.log.info("Materializing asset: gold_dim_hubs")
    service = GoldTransformationService()
    result = service.transform_dim_hubs()
    return Output(
        value=result,
        metadata={
            "target_table": MetadataValue.text(result.get("target_table", "")),
            "schema_layer": MetadataValue.text("GOLD"),
            "grain": MetadataValue.text("One row per logistics distribution hub"),
            "upstream_assets": MetadataValue.text("silver_weather_metrics"),
            "rows_affected": MetadataValue.int(result.get("rows_affected", 0)),
        },
    )


# -----------------------------------------------------------------------------
# Gold Facts
# -----------------------------------------------------------------------------


@asset(
    group_name="gold",
    description="Transactional sell-out fact resolving partner, SKU, and date dimensions.",
    compute_kind="snowflake",
)
def gold_fact_sellout(
    context: AssetExecutionContext,
    silver_invoices: dict[str, Any],
    silver_invoice_items: dict[str, Any],
    gold_dim_date: dict[str, Any],
    gold_dim_partners: dict[str, Any],
    gold_dim_skus: dict[str, Any],
) -> Output[dict[str, Any]]:
    """Materialize B2B sell-out transactional fact table in Snowflake Gold layer."""
    context.log.info("Materializing asset: gold_fact_sellout")
    service = GoldTransformationService()
    result = service.transform_fact_sellout()
    return Output(
        value=result,
        metadata={
            "target_table": MetadataValue.text(result.get("target_table", "")),
            "schema_layer": MetadataValue.text("GOLD"),
            "grain": MetadataValue.text("One row per invoice line item"),
            "upstream_assets": MetadataValue.text(
                "silver_invoices, silver_invoice_items, gold_dim_date, "
                "gold_dim_partners, gold_dim_skus"
            ),
            "rows_affected": MetadataValue.int(result.get("rows_affected", 0)),
        },
    )


@asset(
    group_name="gold",
    description="Periodic inventory snapshot fact recording warehouse stock balances.",
    compute_kind="snowflake",
)
def gold_fact_inventory_snapshot(
    context: AssetExecutionContext,
    silver_partner_inventory: dict[str, Any],
    gold_dim_date: dict[str, Any],
    gold_dim_partners: dict[str, Any],
    gold_dim_skus: dict[str, Any],
) -> Output[dict[str, Any]]:
    """Materialize periodic warehouse inventory snapshot fact in Snowflake Gold layer."""
    context.log.info("Materializing asset: gold_fact_inventory_snapshot")
    service = GoldTransformationService()
    result = service.transform_fact_inventory_snapshot()
    return Output(
        value=result,
        metadata={
            "target_table": MetadataValue.text(result.get("target_table", "")),
            "schema_layer": MetadataValue.text("GOLD"),
            "grain": MetadataValue.text(
                "One row per partner, sku, batch, warehouse, and snapshot date"
            ),
            "upstream_assets": MetadataValue.text(
                "silver_partner_inventory, gold_dim_date, gold_dim_partners, gold_dim_skus"
            ),
            "rows_affected": MetadataValue.int(result.get("rows_affected", 0)),
        },
    )


@asset(
    group_name="gold",
    description="Competitor pricing intelligence fact with unit price per ml metrics.",
    compute_kind="snowflake",
)
def gold_fact_competitor_pricing(
    context: AssetExecutionContext,
    silver_competitor_prices: dict[str, Any],
    gold_dim_date: dict[str, Any],
) -> Output[dict[str, Any]]:
    """Materialize competitor pricing fact table in Snowflake Gold layer."""
    context.log.info("Materializing asset: gold_fact_competitor_pricing")
    service = GoldTransformationService()
    result = service.transform_fact_competitor_pricing()
    return Output(
        value=result,
        metadata={
            "target_table": MetadataValue.text(result.get("target_table", "")),
            "schema_layer": MetadataValue.text("GOLD"),
            "grain": MetadataValue.text("One row per competitor price observation"),
            "upstream_assets": MetadataValue.text("silver_competitor_prices, gold_dim_date"),
            "rows_affected": MetadataValue.int(result.get("rows_affected", 0)),
        },
    )
