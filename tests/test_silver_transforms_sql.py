"""Unit tests for Silver layer SQL push-down query builders."""

import pytest

from src.transformation.sql.silver_transforms import (
    build_merge_competitor_prices_sql,
    build_merge_invoice_items_sql,
    build_merge_invoices_sql,
    build_merge_partner_inventory_sql,
    build_merge_weather_metrics_sql,
    get_all_silver_merge_queries,
)


def test_build_merge_invoices_sql_structure() -> None:
    """Verify generated MERGE statement for SILVER.INVOICES."""
    sql = build_merge_invoices_sql("AURA_LAKEHOUSE")

    assert "MERGE INTO AURA_LAKEHOUSE.SILVER.INVOICES AS target" in sql
    assert "FROM AURA_LAKEHOUSE.BRONZE.INVOICES_RAW" in sql
    assert "QUALIFY ROW_NUMBER() OVER (" in sql
    assert "PARTITION BY payload:metadata:invoice_number::VARCHAR" in sql
    assert "payload:metadata:partner_id::VARCHAR" in sql
    assert "ORDER BY ingested_at DESC" in sql
    assert "WHEN MATCHED THEN" in sql
    assert "UPDATE SET" in sql
    assert "WHEN NOT MATCHED THEN" in sql
    assert "INSERT (" in sql
    assert "CURRENT_TIMESTAMP()" in sql


def test_build_merge_invoice_items_sql_structure() -> None:
    """Verify generated MERGE statement for SILVER.INVOICE_ITEMS with FLATTEN."""
    sql = build_merge_invoice_items_sql("AURA_LAKEHOUSE")

    assert "MERGE INTO AURA_LAKEHOUSE.SILVER.INVOICE_ITEMS AS target" in sql
    assert "FROM AURA_LAKEHOUSE.BRONZE.INVOICES_RAW," in sql
    assert "LATERAL FLATTEN(INPUT => payload:items) AS item" in sql
    assert "QUALIFY ROW_NUMBER() OVER (" in sql
    assert "item.value:sku::VARCHAR" in sql
    assert "item.value:batch_number::VARCHAR" in sql
    assert "ON target.invoice_number = src.invoice_number" in sql
    assert "AND target.sku = src.sku" in sql
    assert "AND target.batch_number = src.batch_number" in sql


def test_build_merge_competitor_prices_sql_structure() -> None:
    """Verify generated MERGE statement for SILVER.COMPETITOR_PRICES."""
    sql = build_merge_competitor_prices_sql("AURA_LAKEHOUSE")

    assert "MERGE INTO AURA_LAKEHOUSE.SILVER.COMPETITOR_PRICES AS target" in sql
    assert "FROM AURA_LAKEHOUSE.BRONZE.COMPETITOR_PRICES_RAW" in sql
    assert "QUALIFY ROW_NUMBER() OVER (" in sql
    assert "competitor_brand" in sql
    assert "payload:product_title::VARCHAR" in sql
    assert "payload:timestamp::TIMESTAMP_NTZ" in sql
    assert "payload:volume_ml::NUMBER(10, 0) AS volume_ml" in sql
    assert "payload:price_brl::NUMBER(10, 2) AS price_brl" in sql
    assert "ON target.competitor_brand = src.competitor_brand" in sql
    assert "AND target.product_title = src.product_title" in sql


def test_build_merge_weather_metrics_sql_structure() -> None:
    """Verify generated MERGE statement for SILVER.WEATHER_METRICS."""
    sql = build_merge_weather_metrics_sql("AURA_LAKEHOUSE")

    assert "MERGE INTO AURA_LAKEHOUSE.SILVER.WEATHER_METRICS AS target" in sql
    assert "FROM AURA_LAKEHOUSE.BRONZE.WEATHER_METRICS_RAW" in sql
    assert "QUALIFY ROW_NUMBER() OVER (" in sql
    assert "PARTITION BY city_hub, payload:date::DATE" in sql
    assert "payload:temp_max::NUMBER(5, 2) AS temp_max" in sql
    assert "payload:precipitation_sum::NUMBER(7, 2) AS precipitation_sum" in sql
    assert "ON target.city_hub = src.city_hub" in sql
    assert "AND target.metric_date = src.metric_date" in sql


def test_build_merge_partner_inventory_sql_structure() -> None:
    """Verify generated MERGE statement for SILVER.PARTNER_INVENTORY."""
    sql = build_merge_partner_inventory_sql("AURA_LAKEHOUSE")

    assert "MERGE INTO AURA_LAKEHOUSE.SILVER.PARTNER_INVENTORY AS target" in sql
    assert "FROM AURA_LAKEHOUSE.BRONZE.PARTNER_INVENTORY_RAW" in sql
    assert "QUALIFY ROW_NUMBER() OVER (" in sql
    assert "payload:sku::VARCHAR" in sql
    assert "payload:batch_id::VARCHAR" in sql
    assert "payload:warehouse_location::VARCHAR" in sql
    assert "payload:snapshot_date::DATE" in sql
    assert "ON target.partner_id = src.partner_id" in sql
    assert "AND target.warehouse_location = src.warehouse_location" in sql


def test_custom_database_substitution() -> None:
    """Verify dynamic database name substitution across generated SQL queries."""
    custom_db = "PROD_LAKEHOUSE"
    invoices_sql = build_merge_invoices_sql(custom_db)
    weather_sql = build_merge_weather_metrics_sql(custom_db)

    assert "MERGE INTO PROD_LAKEHOUSE.SILVER.INVOICES" in invoices_sql
    assert "FROM PROD_LAKEHOUSE.BRONZE.INVOICES_RAW" in invoices_sql
    assert "MERGE INTO PROD_LAKEHOUSE.SILVER.WEATHER_METRICS" in weather_sql
    assert "FROM PROD_LAKEHOUSE.BRONZE.WEATHER_METRICS_RAW" in weather_sql


def test_invalid_database_identifier_rejection() -> None:
    """Verify that malformed database identifiers raise ValueError."""
    with pytest.raises(ValueError, match="Invalid database identifier"):
        build_merge_invoices_sql("AURA; DROP TABLE USERS")

    with pytest.raises(ValueError, match="Invalid database identifier"):
        build_merge_weather_metrics_sql("DB-NAME-WITH-DASH")


def test_get_all_silver_merge_queries() -> None:
    """Verify get_all_silver_merge_queries dictionary completeness."""
    queries = get_all_silver_merge_queries("TEST_DB")

    expected_keys = {
        "invoices",
        "invoice_items",
        "competitor_prices",
        "weather_metrics",
        "partner_inventory",
    }
    assert set(queries.keys()) == expected_keys
    for _key, q in queries.items():
        assert q.startswith("MERGE INTO TEST_DB.SILVER.")
