"""Gold layer transformation service executing dimensional star schema pushdown SQL.

Orchestrates Kimball dimensional modeling transformations from Silver conformed tables
into Gold dimensions and facts using Snowflake pushdown SQL in strict dependency order.
"""

import logging
from types import TracebackType
from typing import Any

from src.common.config import get_settings
from src.common.snowflake_client import SnowflakeClient
from src.transformation.sql.gold_transforms import (
    build_dim_date_sql,
    build_dim_hubs_sql,
    build_dim_partners_sql,
    build_dim_skus_sql,
    build_fact_competitor_pricing_sql,
    build_fact_inventory_snapshot_sql,
    build_fact_sellout_sql,
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


class GoldTransformationService:
    """Service orchestrating Snowflake pushdown SQL transformations for Gold layer.

    Attributes:
        client: Active SnowflakeClient instance.
        database: Target Snowflake database name.
    """

    def __init__(
        self,
        client: SnowflakeClient | None = None,
        database: str | None = None,
    ) -> None:
        """Initialize GoldTransformationService.

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
            Exception: Re-raises any execution failure after logging and rollback.
        """
        logger.info("Executing Gold transform: %s", description)

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

    # -------------------------------------------------------------------------
    # Dimensions (Must be populated before Facts)
    # -------------------------------------------------------------------------

    def transform_dim_date(self) -> dict[str, Any]:
        """Populate or update GOLD.DIM_DATE calendar sequence.

        Returns:
            dict[str, Any]: Execution result summary for dim_date.
        """
        sql = build_dim_date_sql(self._database)
        target = f"{self._database}.GOLD.DIM_DATE"
        rows = self._execute_merge(sql, f"Merge into {target}")
        return {
            "status": "success",
            "target_table": target,
            "rows_affected": rows,
        }

    def transform_dim_partners(self) -> dict[str, Any]:
        """Extract and normalize partners into GOLD.DIM_PARTNERS.

        Returns:
            dict[str, Any]: Execution result summary for dim_partners.
        """
        sql = build_dim_partners_sql(self._database)
        target = f"{self._database}.GOLD.DIM_PARTNERS"
        rows = self._execute_merge(sql, f"Merge into {target}")
        return {
            "status": "success",
            "target_table": target,
            "rows_affected": rows,
        }

    def transform_dim_skus(self) -> dict[str, Any]:
        """Conform product catalogue into GOLD.DIM_SKUS.

        Returns:
            dict[str, Any]: Execution result summary for dim_skus.
        """
        sql = build_dim_skus_sql(self._database)
        target = f"{self._database}.GOLD.DIM_SKUS"
        rows = self._execute_merge(sql, f"Merge into {target}")
        return {
            "status": "success",
            "target_table": target,
            "rows_affected": rows,
        }

    def transform_dim_hubs(self) -> dict[str, Any]:
        """Populate logistics distribution hubs into GOLD.DIM_HUBS.

        Returns:
            dict[str, Any]: Execution result summary for dim_hubs.
        """
        sql = build_dim_hubs_sql(self._database)
        target = f"{self._database}.GOLD.DIM_HUBS"
        rows = self._execute_merge(sql, f"Merge into {target}")
        return {
            "status": "success",
            "target_table": target,
            "rows_affected": rows,
        }

    def transform_dimensions(self) -> dict[str, Any]:
        """Execute all Gold dimension transforms in dependency order.

        Returns:
            dict[str, Any]: Combined execution result for dimensions.
        """
        logger.info("Executing Gold dimension transforms...")
        date_res = self.transform_dim_date()
        partners_res = self.transform_dim_partners()
        skus_res = self.transform_dim_skus()
        hubs_res = self.transform_dim_hubs()

        total_rows = (
            date_res["rows_affected"]
            + partners_res["rows_affected"]
            + skus_res["rows_affected"]
            + hubs_res["rows_affected"]
        )
        return {
            "status": "success",
            "dimensions": {
                "dim_date": date_res,
                "dim_partners": partners_res,
                "dim_skus": skus_res,
                "dim_hubs": hubs_res,
            },
            "total_rows_affected": total_rows,
        }

    # -------------------------------------------------------------------------
    # Facts (Populated after Dimensions)
    # -------------------------------------------------------------------------

    def transform_fact_sellout(self) -> dict[str, Any]:
        """Denormalize invoices and populate GOLD.FACT_SELLOUT.

        Returns:
            dict[str, Any]: Execution result summary for fact_sellout.
        """
        sql = build_fact_sellout_sql(self._database)
        target = f"{self._database}.GOLD.FACT_SELLOUT"
        rows = self._execute_merge(sql, f"Merge into {target}")
        return {
            "status": "success",
            "target_table": target,
            "rows_affected": rows,
        }

    def transform_fact_inventory_snapshot(self) -> dict[str, Any]:
        """Snapshot partner warehouse balances into GOLD.FACT_INVENTORY_SNAPSHOT.

        Returns:
            dict[str, Any]: Execution result summary for fact_inventory_snapshot.
        """
        sql = build_fact_inventory_snapshot_sql(self._database)
        target = f"{self._database}.GOLD.FACT_INVENTORY_SNAPSHOT"
        rows = self._execute_merge(sql, f"Merge into {target}")
        return {
            "status": "success",
            "target_table": target,
            "rows_affected": rows,
        }

    def transform_fact_competitor_pricing(self) -> dict[str, Any]:
        """Compute price per ml and populate GOLD.FACT_COMPETITOR_PRICING.

        Returns:
            dict[str, Any]: Execution result summary for fact_competitor_pricing.
        """
        sql = build_fact_competitor_pricing_sql(self._database)
        target = f"{self._database}.GOLD.FACT_COMPETITOR_PRICING"
        rows = self._execute_merge(sql, f"Merge into {target}")
        return {
            "status": "success",
            "target_table": target,
            "rows_affected": rows,
        }

    def transform_facts(self) -> dict[str, Any]:
        """Execute all Gold fact transforms in dependency order.

        Returns:
            dict[str, Any]: Combined execution result for facts.
        """
        logger.info("Executing Gold fact transforms...")
        sellout_res = self.transform_fact_sellout()
        inventory_res = self.transform_fact_inventory_snapshot()
        competitor_res = self.transform_fact_competitor_pricing()

        total_rows = (
            sellout_res["rows_affected"]
            + inventory_res["rows_affected"]
            + competitor_res["rows_affected"]
        )
        return {
            "status": "success",
            "facts": {
                "fact_sellout": sellout_res,
                "fact_inventory_snapshot": inventory_res,
                "fact_competitor_pricing": competitor_res,
            },
            "total_rows_affected": total_rows,
        }

    def transform_all(self) -> dict[str, Any]:
        """Execute all Gold dimensional models in strict order: Dimensions first, then Facts.

        Returns:
            dict[str, Any]: Full execution summary across all Gold datasets.
        """
        logger.info("Initiating full Gold layer star-schema transformation run...")
        dim_res = self.transform_dimensions()
        fact_res = self.transform_facts()

        return {
            "status": "success",
            "dimensions": dim_res["dimensions"],
            "facts": fact_res["facts"],
            "total_rows_affected": (
                dim_res["total_rows_affected"] + fact_res["total_rows_affected"]
            ),
        }

    def __enter__(self) -> "GoldTransformationService":
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
