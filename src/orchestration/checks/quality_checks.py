"""Dagster Asset Checks for Snowflake Gold Layer Data Quality.

Provides automated assertions for foreign key referential integrity, non-nullability,
revenue positivity, inventory non-negativity, and competitor unit pricing bounds.
"""

import logging
from typing import Any

from dagster import (
    AssetCheckExecutionContext,
    AssetCheckResult,
    AssetCheckSeverity,
    MetadataValue,
    asset_check,
)

from src.common.config import get_settings
from src.common.snowflake_client import SnowflakeClient
from src.orchestration.assets.gold import (
    gold_fact_competitor_pricing,
    gold_fact_inventory_snapshot,
    gold_fact_sellout,
)

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Query Execution Helpers
# -----------------------------------------------------------------------------


def query_sellout_null_surrogate_keys(cursor: Any, database: str = "AURA_LAKEHOUSE") -> int:
    """Execute query checking for NULL surrogate keys in FACT_SELLOUT.

    Args:
        cursor: Database cursor to execute on.
        database: Snowflake database name.

    Returns:
        int: Number of rows violating the non-null constraint.
    """
    sql = f"""
    SELECT COUNT(*)
    FROM {database}.GOLD.FACT_SELLOUT
    WHERE partner_key IS NULL
       OR sku_key IS NULL
       OR date_key IS NULL
    """
    cursor.execute(sql)
    row = cursor.fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def query_sellout_negative_revenue(cursor: Any, database: str = "AURA_LAKEHOUSE") -> int:
    """Execute query checking for negative revenue in FACT_SELLOUT.

    Args:
        cursor: Database cursor to execute on.
        database: Snowflake database name.

    Returns:
        int: Number of rows with negative total_price or net_revenue.
    """
    sql = f"""
    SELECT COUNT(*)
    FROM {database}.GOLD.FACT_SELLOUT
    WHERE total_price < 0
       OR net_revenue < 0
    """
    cursor.execute(sql)
    row = cursor.fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def query_inventory_negative_balances(cursor: Any, database: str = "AURA_LAKEHOUSE") -> int:
    """Execute query checking for negative stock balances in FACT_INVENTORY_SNAPSHOT.

    Args:
        cursor: Database cursor to execute on.
        database: Snowflake database name.

    Returns:
        int: Number of rows with stock_quantity < 0.
    """
    sql = f"""
    SELECT COUNT(*)
    FROM {database}.GOLD.FACT_INVENTORY_SNAPSHOT
    WHERE stock_quantity < 0
    """
    cursor.execute(sql)
    row = cursor.fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def query_competitor_invalid_price_bounds(cursor: Any, database: str = "AURA_LAKEHOUSE") -> int:
    """Execute query checking for invalid unit price bounds in FACT_COMPETITOR_PRICING.

    Args:
        cursor: Database cursor to execute on.
        database: Snowflake database name.

    Returns:
        int: Number of rows with price_per_ml <= 0.
    """
    sql = f"""
    SELECT COUNT(*)
    FROM {database}.GOLD.FACT_COMPETITOR_PRICING
    WHERE price_per_ml <= 0
    """
    cursor.execute(sql)
    row = cursor.fetchone()
    return int(row[0]) if row and row[0] is not None else 0


# -----------------------------------------------------------------------------
# Dagster Asset Checks
# -----------------------------------------------------------------------------


@asset_check(
    asset=gold_fact_sellout,
    description="Asserts zero nulls in FACT_SELLOUT surrogate keys (partner, sku, date).",
)
def check_sellout_surrogate_keys_not_null(
    context: AssetCheckExecutionContext,
) -> AssetCheckResult:
    """Check that all surrogate keys in FACT_SELLOUT are non-null."""
    context.log.info("Executing asset check: check_sellout_surrogate_keys_not_null")
    db = get_settings().database
    client = SnowflakeClient()

    with client.get_cursor() as cursor:
        violations = query_sellout_null_surrogate_keys(cursor, database=db)

    passed = violations == 0
    description = (
        "All foreign surrogate keys in FACT_SELLOUT are populated."
        if passed
        else f"Found {violations} row(s) with NULL surrogate keys in {db}.GOLD.FACT_SELLOUT"
    )

    return AssetCheckResult(
        passed=passed,
        severity=AssetCheckSeverity.ERROR,
        description=description,
        metadata={
            "target_table": MetadataValue.text(f"{db}.GOLD.FACT_SELLOUT"),
            "violations": MetadataValue.int(violations),
            "checked_keys": MetadataValue.text("partner_key, sku_key, date_key"),
        },
    )


@asset_check(
    asset=gold_fact_sellout,
    description="Asserts total_amount >= 0 across all sell-out transactions.",
)
def check_sellout_positive_revenue(
    context: AssetCheckExecutionContext,
) -> AssetCheckResult:
    """Check that all sell-out transactions in FACT_SELLOUT have non-negative revenue."""
    context.log.info("Executing asset check: check_sellout_positive_revenue")
    db = get_settings().database
    client = SnowflakeClient()

    with client.get_cursor() as cursor:
        violations = query_sellout_negative_revenue(cursor, database=db)

    passed = violations == 0
    description = (
        "All sell-out transactions have non-negative revenue (total_price >= 0, net_revenue >= 0)."
        if passed
        else f"Found {violations} transaction(s) with negative revenue in {db}.GOLD.FACT_SELLOUT"
    )

    return AssetCheckResult(
        passed=passed,
        severity=AssetCheckSeverity.ERROR,
        description=description,
        metadata={
            "target_table": MetadataValue.text(f"{db}.GOLD.FACT_SELLOUT"),
            "violations": MetadataValue.int(violations),
            "checked_columns": MetadataValue.text("total_price, net_revenue"),
        },
    )


@asset_check(
    asset=gold_fact_inventory_snapshot,
    description="Asserts stock_quantity >= 0 on FACT_INVENTORY_SNAPSHOT.",
)
def check_inventory_non_negative_balances(
    context: AssetCheckExecutionContext,
) -> AssetCheckResult:
    """Check that warehouse inventory snapshots contain non-negative stock balances."""
    context.log.info("Executing asset check: check_inventory_non_negative_balances")
    db = get_settings().database
    client = SnowflakeClient()

    with client.get_cursor() as cursor:
        violations = query_inventory_negative_balances(cursor, database=db)

    passed = violations == 0
    description = (
        "All warehouse inventory snapshots have non-negative stock balances (stock_quantity >= 0)."
        if passed
        else (
            f"Found {violations} snapshot(s) with negative stock in "
            f"{db}.GOLD.FACT_INVENTORY_SNAPSHOT"
        )
    )

    return AssetCheckResult(
        passed=passed,
        severity=AssetCheckSeverity.ERROR,
        description=description,
        metadata={
            "target_table": MetadataValue.text(f"{db}.GOLD.FACT_INVENTORY_SNAPSHOT"),
            "violations": MetadataValue.int(violations),
            "checked_column": MetadataValue.text("stock_quantity"),
        },
    )


@asset_check(
    asset=gold_fact_competitor_pricing,
    description="Asserts price_per_ml > 0 on FACT_COMPETITOR_PRICING.",
)
def check_competitor_price_bounds(
    context: AssetCheckExecutionContext,
) -> AssetCheckResult:
    """Check that competitor pricing records have valid positive price per milliliter."""
    context.log.info("Executing asset check: check_competitor_price_bounds")
    db = get_settings().database
    client = SnowflakeClient()

    with client.get_cursor() as cursor:
        violations = query_competitor_invalid_price_bounds(cursor, database=db)

    passed = violations == 0
    description = (
        "All competitor pricing observations satisfy price_per_ml > 0."
        if passed
        else (
            f"Found {violations} record(s) violating price_per_ml > 0 in "
            f"{db}.GOLD.FACT_COMPETITOR_PRICING"
        )
    )

    return AssetCheckResult(
        passed=passed,
        severity=AssetCheckSeverity.ERROR,
        description=description,
        metadata={
            "target_table": MetadataValue.text(f"{db}.GOLD.FACT_COMPETITOR_PRICING"),
            "violations": MetadataValue.int(violations),
            "checked_column": MetadataValue.text("price_per_ml"),
        },
    )
