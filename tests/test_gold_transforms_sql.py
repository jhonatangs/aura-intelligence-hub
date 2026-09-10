"""Unit tests for Gold layer dimensional SQL push-down query builders."""

import pytest

from src.transformation.sql.gold_transforms import (
    build_dim_date_sql,
    build_dim_hubs_sql,
    build_dim_partners_sql,
    build_dim_skus_sql,
    build_fact_competitor_pricing_sql,
    build_fact_inventory_snapshot_sql,
    build_fact_sellout_sql,
    get_all_gold_dimension_queries,
    get_all_gold_fact_queries,
    get_all_gold_queries,
)


def test_build_dim_date_sql_structure() -> None:
    """Verify generated MERGE statement for GOLD.DIM_DATE calendar spine."""
    sql = build_dim_date_sql("AURA_LAKEHOUSE")

    assert "MERGE INTO AURA_LAKEHOUSE.GOLD.DIM_DATE AS target" in sql
    assert "TABLE(GENERATOR(ROWCOUNT => 1826))" in sql
    assert "TO_NUMBER(TO_VARCHAR(calendar_date, 'YYYYMMDD')) AS date_key" in sql
    assert "YEAR(calendar_date)::NUMBER(4, 0) AS year" in sql
    assert "QUARTER(calendar_date)::NUMBER(1, 0) AS quarter" in sql
    assert "MONTH(calendar_date)::NUMBER(2, 0) AS month" in sql
    assert "DAYOFWEEK(calendar_date)::NUMBER(1, 0) AS day_of_week" in sql
    assert "is_weekend" in sql
    assert "is_holiday" in sql
    assert "ON target.date_key = src.date_key" in sql
    assert "WHEN MATCHED THEN" in sql
    assert "WHEN NOT MATCHED THEN" in sql


def test_build_dim_partners_sql_structure() -> None:
    """Verify generated MERGE statement for GOLD.DIM_PARTNERS."""
    sql = build_dim_partners_sql("AURA_LAKEHOUSE")

    assert "MERGE INTO AURA_LAKEHOUSE.GOLD.DIM_PARTNERS AS target" in sql
    assert "FROM AURA_LAKEHOUSE.SILVER.INVOICES" in sql
    assert "FROM AURA_LAKEHOUSE.SILVER.PARTNER_INVENTORY" in sql
    assert "MD5(partner_id) AS partner_key" in sql
    assert "COALESCE(partner_cnpj, 'UNKNOWN') AS partner_cnpj" in sql
    assert "CONCAT('Partner ', partner_id) AS partner_name" in sql
    assert "ON target.partner_key = src.partner_key" in sql
    assert "WHEN MATCHED THEN" in sql
    assert "WHEN NOT MATCHED THEN" in sql


def test_build_dim_skus_sql_structure() -> None:
    """Verify generated MERGE statement for GOLD.DIM_SKUS with catalog attributes."""
    sql = build_dim_skus_sql("AURA_LAKEHOUSE")

    assert "MERGE INTO AURA_LAKEHOUSE.GOLD.DIM_SKUS AS target" in sql
    assert "FROM AURA_LAKEHOUSE.SILVER.INVOICE_ITEMS" in sql
    assert "FROM AURA_LAKEHOUSE.SILVER.PARTNER_INVENTORY" in sql
    assert "MD5(sku) AS sku_key" in sql
    assert "AURA_250ML" in sql
    assert "AURA_ZERO_250ML" in sql
    assert "AURA_TROPICAL_473ML" in sql
    assert "volume_ml" in sql
    assert "flavor" in sql
    assert "package_type" in sql
    assert "ON target.sku_key = src.sku_key" in sql


def test_build_dim_hubs_sql_structure() -> None:
    """Verify generated MERGE statement for GOLD.DIM_HUBS with hub registry values."""
    sql = build_dim_hubs_sql("AURA_LAKEHOUSE")

    assert "MERGE INTO AURA_LAKEHOUSE.GOLD.DIM_HUBS AS target" in sql
    assert "HUB-SP" in sql
    assert "São Paulo Central Hub" in sql
    assert "HUB-RJ" in sql
    assert "HUB-BH" in sql
    assert "MD5(column1) AS hub_key" in sql
    assert "column5::NUMBER(10, 6) AS latitude" in sql
    assert "column6::NUMBER(10, 6) AS longitude" in sql
    assert "ON target.hub_key = src.hub_key" in sql


def test_build_fact_sellout_sql_structure() -> None:
    """Verify generated MERGE statement for GOLD.FACT_SELLOUT."""
    sql = build_fact_sellout_sql("AURA_LAKEHOUSE")

    assert "MERGE INTO AURA_LAKEHOUSE.GOLD.FACT_SELLOUT AS target" in sql
    assert "FROM AURA_LAKEHOUSE.SILVER.INVOICE_ITEMS itm" in sql
    assert "JOIN AURA_LAKEHOUSE.SILVER.INVOICES inv" in sql
    assert "MD5(itm.partner_id) AS partner_key" in sql
    assert "MD5(itm.sku) AS sku_key" in sql
    assert "sellout_key" in sql
    assert "quantity_sold" in sql
    assert "net_revenue" in sql
    assert "QUALIFY ROW_NUMBER() OVER (" in sql
    assert "ON target.sellout_key = src.sellout_key" in sql


def test_build_fact_inventory_snapshot_sql_structure() -> None:
    """Verify generated MERGE statement for GOLD.FACT_INVENTORY_SNAPSHOT."""
    sql = build_fact_inventory_snapshot_sql("AURA_LAKEHOUSE")

    assert "MERGE INTO AURA_LAKEHOUSE.GOLD.FACT_INVENTORY_SNAPSHOT AS target" in sql
    assert "FROM AURA_LAKEHOUSE.SILVER.PARTNER_INVENTORY" in sql
    assert "MD5(partner_id) AS partner_key" in sql
    assert "MD5(sku) AS sku_key" in sql
    assert "snapshot_key" in sql
    assert "warehouse_location" in sql
    assert "stock_quantity" in sql
    assert "QUALIFY ROW_NUMBER() OVER (" in sql
    assert "ON target.snapshot_key = src.snapshot_key" in sql


def test_build_fact_competitor_pricing_sql_structure() -> None:
    """Verify generated MERGE statement for GOLD.FACT_COMPETITOR_PRICING."""
    sql = build_fact_competitor_pricing_sql("AURA_LAKEHOUSE")

    assert "MERGE INTO AURA_LAKEHOUSE.GOLD.FACT_COMPETITOR_PRICING AS target" in sql
    assert "FROM AURA_LAKEHOUSE.SILVER.COMPETITOR_PRICES" in sql
    assert "ROUND(price_brl / NULLIF(volume_ml, 0), 4) AS price_per_ml" in sql
    assert "pricing_key" in sql
    assert "is_in_stock" in sql
    assert "QUALIFY ROW_NUMBER() OVER (" in sql
    assert "ON target.pricing_key = src.pricing_key" in sql


def test_custom_database_substitution() -> None:
    """Verify dynamic database name substitution across all Gold queries."""
    custom_db = "PROD_LAKEHOUSE"
    date_sql = build_dim_date_sql(custom_db)
    partners_sql = build_dim_partners_sql(custom_db)
    sellout_sql = build_fact_sellout_sql(custom_db)

    assert "MERGE INTO PROD_LAKEHOUSE.GOLD.DIM_DATE" in date_sql
    assert "MERGE INTO PROD_LAKEHOUSE.GOLD.DIM_PARTNERS" in partners_sql
    assert "FROM PROD_LAKEHOUSE.SILVER.INVOICES" in partners_sql
    assert "MERGE INTO PROD_LAKEHOUSE.GOLD.FACT_SELLOUT" in sellout_sql


def test_invalid_database_identifier_rejection() -> None:
    """Verify that malformed database identifiers raise ValueError."""
    with pytest.raises(ValueError, match="Invalid database identifier"):
        build_dim_date_sql("AURA; DROP TABLE GOLD")

    with pytest.raises(ValueError, match="Invalid database identifier"):
        build_fact_sellout_sql("DB-INVALID-DASH")


def test_get_all_gold_query_dictionaries() -> None:
    """Verify completeness of dimension, fact, and combined query dictionaries."""
    dim_queries = get_all_gold_dimension_queries("TEST_DB")
    fact_queries = get_all_gold_fact_queries("TEST_DB")
    all_queries = get_all_gold_queries("TEST_DB")

    expected_dims = {"dim_date", "dim_partners", "dim_skus", "dim_hubs"}
    expected_facts = {"fact_sellout", "fact_inventory_snapshot", "fact_competitor_pricing"}

    assert set(dim_queries.keys()) == expected_dims
    assert set(fact_queries.keys()) == expected_facts
    assert set(all_queries.keys()) == expected_dims | expected_facts

    for _key, q in all_queries.items():
        assert q.startswith("MERGE INTO TEST_DB.GOLD.")
