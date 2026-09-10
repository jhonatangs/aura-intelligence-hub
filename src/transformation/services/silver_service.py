"""Silver layer transformation service executing pushdown SQL transformations.

Orchestrates normalization, deduplication, and schema conformation from Bronze
raw variant payloads into Silver conformed tables using Snowflake pushdown SQL.
"""

import logging
from types import TracebackType
from typing import Any

from src.common.config import get_settings
from src.common.snowflake_client import SnowflakeClient
from src.transformation.sql.silver_transforms import (
    build_merge_competitor_prices_sql,
    build_merge_invoice_items_sql,
    build_merge_invoices_sql,
    build_merge_partner_inventory_sql,
    build_merge_weather_metrics_sql,
)

logger = logging.getLogger(__name__)


def _extract_rows_affected(cursor: Any) -> int:
    """Extract affected row count from cursor after MERGE execution.

    Args:
        cursor: Executed database cursor.

    Returns:
        int: Number of affected (inserted/updated) rows.
    """
    if hasattr(cursor, "rowcount") and cursor.rowcount and cursor.rowcount > 0:
        return int(cursor.rowcount)
    if hasattr(cursor, "description") and cursor.description:
        try:
            row = cursor.fetchone()
            if row and isinstance(row, (tuple, list)):
                return sum(val for val in row if isinstance(val, int))
        except Exception:
            pass
    return 0


class SilverTransformationService:
    """Service orchestrating Snowflake pushdown SQL transformations for Silver layer.

    Attributes:
        client: Active SnowflakeClient instance.
        database: Target Snowflake database name.
    """

    def __init__(
        self,
        client: SnowflakeClient | None = None,
        database: str | None = None,
    ) -> None:
        """Initialize SilverTransformationService.

        Args:
            client: Optional SnowflakeClient instance. Defaults to new instance.
            database: Optional Snowflake database name. Defaults to configured database.
        """
        self._client = client or SnowflakeClient()
        self._owns_connection = client is None
        self._database = database or self._resolve_database()

    def _resolve_database(self) -> str:
        """Resolve database name from settings with fallback to default.

        Returns:
            str: Resolved database name.
        """
        try:
            return get_settings().database
        except Exception:
            return "AURA_LAKEHOUSE"

    @property
    def client(self) -> SnowflakeClient:
        """Active SnowflakeClient instance."""
        return self._client

    @property
    def database(self) -> str:
        """Target database name."""
        return self._database

    def _execute_merge(self, query: str, description: str) -> int:
        """Execute a single MERGE SQL statement within managed cursor context.

        Args:
            query: SQL statement to execute.
            description: Description of the transformation for logging.

        Returns:
            int: Number of affected rows.

        Raises:
            Exception: Re-raises any execution failure after logging.
        """
        logger.info("Executing Silver transform: %s", description)

        def _do_execute(client: SnowflakeClient) -> int:
            with client.managed_cursor() as cursor:
                try:
                    cursor.execute(query)
                    rows = _extract_rows_affected(cursor)
                    logger.info("Finished %s: %d rows affected", description, rows)
                    return rows
                except Exception as err:
                    logger.error("Failed to execute %s: %s", description, err)
                    try:
                        cursor.execute("ROLLBACK")
                    except Exception:
                        pass
                    raise

        if not self._client.is_connected:
            with self._client:
                return _do_execute(self._client)
        else:
            return _do_execute(self._client)

    def transform_invoices_header(self) -> dict[str, Any]:
        """Normalize Bronze raw invoices into SILVER.INVOICES (header grain).

        Returns:
            dict[str, Any]: Execution results for invoices header.
        """
        sql = build_merge_invoices_sql(self._database)
        target = f"{self._database}.SILVER.INVOICES"
        rows = self._execute_merge(sql, f"Merge into {target}")
        return {
            "status": "success",
            "target_table": target,
            "rows_affected": rows,
        }

    def transform_invoice_items(self) -> dict[str, Any]:
        """Flatten and normalize Bronze raw invoice items into SILVER.INVOICE_ITEMS.

        Returns:
            dict[str, Any]: Execution results for invoice line items.
        """
        sql = build_merge_invoice_items_sql(self._database)
        target = f"{self._database}.SILVER.INVOICE_ITEMS"
        rows = self._execute_merge(sql, f"Merge into {target}")
        return {
            "status": "success",
            "target_table": target,
            "rows_affected": rows,
        }

    def transform_invoices(self) -> dict[str, Any]:
        """Normalize Bronze raw invoices into SILVER.INVOICES and SILVER.INVOICE_ITEMS.

        Returns:
            dict[str, Any]: Execution results for invoices and line items.
        """
        invoices_sql = build_merge_invoices_sql(self._database)
        items_sql = build_merge_invoice_items_sql(self._database)

        def _do_transform(client: SnowflakeClient) -> dict[str, Any]:
            with client.managed_cursor() as cursor:
                try:
                    cursor.execute(invoices_sql)
                    inv_rows = _extract_rows_affected(cursor)

                    cursor.execute(items_sql)
                    item_rows = _extract_rows_affected(cursor)

                    return {
                        "status": "success",
                        "target_tables": [
                            f"{self._database}.SILVER.INVOICES",
                            f"{self._database}.SILVER.INVOICE_ITEMS",
                        ],
                        "invoices_affected": inv_rows,
                        "invoice_items_affected": item_rows,
                        "total_rows_affected": inv_rows + item_rows,
                    }
                except Exception as err:
                    logger.error("Failed transform_invoices: %s", err)
                    try:
                        cursor.execute("ROLLBACK")
                    except Exception:
                        pass
                    raise

        if not self._client.is_connected:
            with self._client:
                return _do_transform(self._client)
        else:
            return _do_transform(self._client)

    def transform_competitor_prices(self) -> dict[str, Any]:
        """Clean and deduplicate scraped prices into SILVER.COMPETITOR_PRICES.

        Returns:
            dict[str, Any]: Execution results for competitor prices.
        """
        sql = build_merge_competitor_prices_sql(self._database)
        target = f"{self._database}.SILVER.COMPETITOR_PRICES"
        rows = self._execute_merge(sql, f"Merge into {target}")
        return {
            "status": "success",
            "target_table": target,
            "rows_affected": rows,
        }

    def transform_weather_metrics(self) -> dict[str, Any]:
        """Type and deduplicate weather observations into SILVER.WEATHER_METRICS.

        Returns:
            dict[str, Any]: Execution results for weather metrics.
        """
        sql = build_merge_weather_metrics_sql(self._database)
        target = f"{self._database}.SILVER.WEATHER_METRICS"
        rows = self._execute_merge(sql, f"Merge into {target}")
        return {
            "status": "success",
            "target_table": target,
            "rows_affected": rows,
        }

    def transform_partner_inventory(self) -> dict[str, Any]:
        """Normalize legacy warehouse inventory into SILVER.PARTNER_INVENTORY.

        Returns:
            dict[str, Any]: Execution results for partner inventory.
        """
        sql = build_merge_partner_inventory_sql(self._database)
        target = f"{self._database}.SILVER.PARTNER_INVENTORY"
        rows = self._execute_merge(sql, f"Merge into {target}")
        return {
            "status": "success",
            "target_table": target,
            "rows_affected": rows,
        }

    def transform_all(self) -> dict[str, Any]:
        """Execute all Silver transformations in topological order.

        Returns:
            dict[str, Any]: Aggregated execution summary across all Silver datasets.
        """
        logger.info("Initiating full Silver layer transformation run...")
        invoices_res = self.transform_invoices()
        competitor_res = self.transform_competitor_prices()
        weather_res = self.transform_weather_metrics()
        inventory_res = self.transform_partner_inventory()

        total_rows = (
            invoices_res["total_rows_affected"]
            + competitor_res["rows_affected"]
            + weather_res["rows_affected"]
            + inventory_res["rows_affected"]
        )

        return {
            "status": "success",
            "datasets": {
                "invoices": invoices_res,
                "competitor_prices": competitor_res,
                "weather_metrics": weather_res,
                "partner_inventory": inventory_res,
            },
            "total_rows_affected": total_rows,
        }

    def __enter__(self) -> "SilverTransformationService":
        """Enter context manager, connecting client if not connected."""
        if not self._client.is_connected:
            self._client.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit context manager, closing client if owned."""
        if self._owns_connection:
            self._client.close()
