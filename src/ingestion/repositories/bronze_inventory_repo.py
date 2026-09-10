"""Repository for landing legacy partner warehouse inventories into Snowflake Bronze layer.

Manages parameterized execution, JSON payload serialization, and metadata tracking
for AURA_LAKEHOUSE.BRONZE.PARTNER_INVENTORY_RAW.
"""

import json
from collections.abc import Sequence
from types import TracebackType
from typing import Any

import snowflake.connector

from src.common.snowflake_client import SnowflakeClient
from src.ingestion.models.multimodal import PartnerInventoryRecord


def get_inventory_insert_sql(paramstyle: str | None = None) -> str:
    """Return parameterized INSERT statement adapting to active connector paramstyle.

    Args:
        paramstyle: Optional explicit paramstyle ('qmark' or 'pyformat').

    Returns:
        str: Parameterized SQL statement.
    """
    style = paramstyle or getattr(snowflake.connector, "paramstyle", "pyformat")
    placeholder = "?" if style == "qmark" else "%s"
    return f"""INSERT INTO AURA_LAKEHOUSE.BRONZE.PARTNER_INVENTORY_RAW (
    source_file,
    partner_id,
    file_hash_md5,
    ingested_at,
    payload
) SELECT {placeholder}, {placeholder}, {placeholder},
         CURRENT_TIMESTAMP(), PARSE_JSON({placeholder})"""


class BronzePartnerInventoryRepository:
    """Repository handling persistence of partner inventory balances into Snowflake Bronze storage.

    Attributes:
        client: Active SnowflakeClient instance.
    """

    def __init__(self, client: SnowflakeClient | None = None) -> None:
        """Initialize repository with Snowflake client.

        Args:
            client: Optional SnowflakeClient instance.
        """
        self._client = client or SnowflakeClient()
        self._owns_connection = client is None

    @property
    def client(self) -> SnowflakeClient:
        """Active SnowflakeClient instance."""
        return self._client

    def insert_inventory_record(
        self,
        source_file: str,
        partner_id: str,
        file_hash_md5: str,
        payload: PartnerInventoryRecord | dict[str, Any],
        paramstyle: str | None = None,
    ) -> None:
        """Persist a single partner inventory record into Snowflake Bronze.

        Args:
            source_file: Source filename or extract identifier.
            partner_id: Unique partner distributor identifier.
            file_hash_md5: MD5 hex digest of the raw source file.
            payload: Validated PartnerInventoryRecord or raw JSON-serializable dictionary.
            paramstyle: Optional parameter placeholder style.
        """
        if isinstance(payload, PartnerInventoryRecord):
            payload_json = payload.model_dump_json()
        elif isinstance(payload, dict):
            payload_json = json.dumps(payload, default=str)
        else:
            raise TypeError(f"Payload must be PartnerInventoryRecord or dict, got {type(payload)}")

        sql = get_inventory_insert_sql(paramstyle)
        params = (source_file, partner_id, file_hash_md5, payload_json)

        if not self._client.is_connected:
            with self._client:
                with self._client.managed_cursor() as cursor:
                    cursor.execute(sql, params)
        else:
            with self._client.managed_cursor() as cursor:
                cursor.execute(sql, params)

    def batch_insert_inventory_records(
        self,
        records: Sequence[tuple[str, str, str, PartnerInventoryRecord | dict[str, Any]]],
        paramstyle: str | None = None,
    ) -> int:
        """Persist multiple inventory records into Snowflake Bronze table.

        Args:
            records: Sequence of (source_file, partner_id, file_hash_md5, payload) tuples.
            paramstyle: Optional parameter placeholder style.

        Returns:
            int: Number of successfully inserted records.
        """
        inserted_count = 0
        sql = get_inventory_insert_sql(paramstyle)

        def _do_batch(client: SnowflakeClient) -> int:
            nonlocal inserted_count
            with client.managed_cursor() as cursor:
                for source_file, partner_id, file_hash_md5, payload in records:
                    if isinstance(payload, PartnerInventoryRecord):
                        payload_json = payload.model_dump_json()
                    elif isinstance(payload, dict):
                        payload_json = json.dumps(payload, default=str)
                    else:
                        raise TypeError(f"Unsupported payload type: {type(payload)}")
                    cursor.execute(sql, (source_file, partner_id, file_hash_md5, payload_json))
                    inserted_count += 1
            return inserted_count

        if not self._client.is_connected:
            with self._client:
                return _do_batch(self._client)
        else:
            return _do_batch(self._client)

    def __enter__(self) -> "BronzePartnerInventoryRepository":
        """Enter context manager."""
        if not self._client.is_connected:
            self._client.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit context manager."""
        if self._owns_connection:
            self._client.close()
