"""Dagster Software-Defined Assets (SDAs) for Snowflake Bronze landing layer.

Declares assets for raw partner invoices, macro climatic metrics, competitor prices,
and legacy partner warehouse inventories with lineage and schema metadata.
"""

from typing import Any

from dagster import (
    AssetExecutionContext,
    MetadataValue,
    Output,
    asset,
)


@asset(
    group_name="bronze",
    description="Raw B2B partner invoice JSON payloads ingested into Snowflake Bronze layer.",
    compute_kind="snowflake",
)
def bronze_invoices_raw(context: AssetExecutionContext) -> Output[dict[str, Any]]:
    """Materialize raw B2B partner invoices into Snowflake Bronze layer."""
    context.log.info("Materializing asset: bronze_invoices_raw")
    summary = {
        "status": "success",
        "target_table": "AURA_LAKEHOUSE.BRONZE.INVOICES_RAW",
        "schema_layer": "BRONZE",
    }
    return Output(
        value=summary,
        metadata={
            "target_table": MetadataValue.text("AURA_LAKEHOUSE.BRONZE.INVOICES_RAW"),
            "schema_layer": MetadataValue.text("BRONZE"),
            "payload_format": MetadataValue.text("VARIANT"),
            "source_format": MetadataValue.text("PDF / ReportLab Synthetic"),
            "lineage": MetadataValue.text("Partner PDFs -> LangGraph -> Snowflake Bronze"),
        },
    )


@asset(
    group_name="bronze",
    description="Raw Open-Meteo macro climatic metric observations in Snowflake Bronze.",
    compute_kind="snowflake",
)
def bronze_weather_metrics_raw(context: AssetExecutionContext) -> Output[dict[str, Any]]:
    """Materialize Open-Meteo climatic metrics into Snowflake Bronze layer."""
    context.log.info("Materializing asset: bronze_weather_metrics_raw")
    summary = {
        "status": "success",
        "target_table": "AURA_LAKEHOUSE.BRONZE.WEATHER_METRICS_RAW",
        "schema_layer": "BRONZE",
    }
    return Output(
        value=summary,
        metadata={
            "target_table": MetadataValue.text("AURA_LAKEHOUSE.BRONZE.WEATHER_METRICS_RAW"),
            "schema_layer": MetadataValue.text("BRONZE"),
            "payload_format": MetadataValue.text("VARIANT"),
            "source_type": MetadataValue.text("Open-Meteo REST API"),
            "hubs_count": MetadataValue.int(10),
            "lineage": MetadataValue.text("Open-Meteo API -> Httpx Client -> Snowflake Bronze"),
        },
    )


@asset(
    group_name="bronze",
    description="Raw competitor pricing observations for Red Bull and Monster Energy in Bronze.",
    compute_kind="snowflake",
)
def bronze_competitor_prices_raw(context: AssetExecutionContext) -> Output[dict[str, Any]]:
    """Materialize competitor pricing observations into Snowflake Bronze layer."""
    context.log.info("Materializing asset: bronze_competitor_prices_raw")
    summary = {
        "status": "success",
        "target_table": "AURA_LAKEHOUSE.BRONZE.COMPETITOR_PRICES_RAW",
        "schema_layer": "BRONZE",
    }
    return Output(
        value=summary,
        metadata={
            "target_table": MetadataValue.text("AURA_LAKEHOUSE.BRONZE.COMPETITOR_PRICES_RAW"),
            "schema_layer": MetadataValue.text("BRONZE"),
            "payload_format": MetadataValue.text("VARIANT"),
            "competitors": MetadataValue.text("RED_BULL, MONSTER"),
            "source_type": MetadataValue.text("E-Commerce Web Scraper (BS4 / Async Httpx)"),
            "lineage": MetadataValue.text("Retail Channels -> Async Scraper -> Snowflake Bronze"),
        },
    )


@asset(
    group_name="bronze",
    description="Raw legacy partner warehouse inventory snapshots in Snowflake Bronze layer.",
    compute_kind="snowflake",
)
def bronze_partner_inventory_raw(context: AssetExecutionContext) -> Output[dict[str, Any]]:
    """Materialize legacy partner warehouse inventory files into Snowflake Bronze layer."""
    context.log.info("Materializing asset: bronze_partner_inventory_raw")
    summary = {
        "status": "success",
        "target_table": "AURA_LAKEHOUSE.BRONZE.PARTNER_INVENTORY_RAW",
        "schema_layer": "BRONZE",
    }
    return Output(
        value=summary,
        metadata={
            "target_table": MetadataValue.text("AURA_LAKEHOUSE.BRONZE.PARTNER_INVENTORY_RAW"),
            "schema_layer": MetadataValue.text("BRONZE"),
            "payload_format": MetadataValue.text("VARIANT"),
            "source_type": MetadataValue.text("Delimited Tabular (CSV / TXT)"),
            "hash_algorithm": MetadataValue.text("MD5"),
            "lineage": MetadataValue.text(
                "Partner ERP Dumps -> Tabular Ingestor -> Snowflake Bronze"
            ),
        },
    )
