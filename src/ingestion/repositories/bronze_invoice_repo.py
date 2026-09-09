"""Repository for landing raw partner invoices into Snowflake Bronze layer.

Manages parameterized execution, JSON payload serialization, and ingestion
metadata tracking for AURA_LAKEHOUSE.BRONZE.INVOICES_RAW.
"""

import json
from collections.abc import Sequence
from types import TracebackType
from typing import Any

import snowflake.connector

from src.common.snowflake_client import SnowflakeClient
from src.ingestion.models.invoice import RawInvoicePayload


def get_insert_sql(paramstyle: str | None = None) -> str:
    """Return parameterized INSERT statement adapting to active connector paramstyle.

    Args:
        paramstyle: Optional explicit paramstyle ('qmark' for '?' or 'pyformat' for '%s').
            Defaults to inspecting snowflake.connector.paramstyle.

    Returns:
        str: Parameterized SQL statement.
    """
    style = paramstyle or getattr(snowflake.connector, "paramstyle", "pyformat")
    placeholder = "?" if style == "qmark" else "%s"
    return f"""INSERT INTO AURA_LAKEHOUSE.BRONZE.INVOICES_RAW (
    source_file,
    partner_id,
    ingested_at,
    payload
) SELECT {placeholder}, {placeholder}, CURRENT_TIMESTAMP(), PARSE_JSON({placeholder})"""


class BronzeInvoiceRepository:
    """Repository handling persistence of raw invoice payloads into Snowflake Bronze storage.

    Attributes:
        client: Active SnowflakeClient instance.
    """

    def __init__(self, client: SnowflakeClient | None = None) -> None:
        """Initialize repository with Snowflake client.

        Args:
            client: Optional SnowflakeClient. Instantiates default client if None.
        """
        self._client = client or SnowflakeClient()
        self._owns_connection = client is None

    @property
    def client(self) -> SnowflakeClient:
        """Active SnowflakeClient instance."""
        return self._client

    def insert_invoice(
        self,
        source_file: str,
        partner_id: str,
        payload: RawInvoicePayload | dict[str, Any],
        paramstyle: str | None = None,
    ) -> None:
        """Persist a single validated invoice payload into Snowflake Bronze.

        Args:
            source_file: Identifier or filename of the source invoice PDF.
            partner_id: Issuing partner organization identifier.
            payload: Validated RawInvoicePayload or raw JSON-serializable dictionary.
            paramstyle: Optional parameter placeholder style ('qmark' or 'pyformat').

        Raises:
            RuntimeError: If connection or insertion fails.
        """
        if isinstance(payload, RawInvoicePayload):
            payload_json = payload.model_dump_json()
        elif isinstance(payload, dict):
            payload_json = json.dumps(payload, default=str)
        else:
            raise TypeError(f"Payload must be RawInvoicePayload or dict, got {type(payload)}")

        sql = get_insert_sql(paramstyle)
        params = (source_file, partner_id, payload_json)

        if not self._client.is_connected:
            with self._client:
                with self._client.managed_cursor() as cursor:
                    cursor.execute(sql, params)
        else:
            with self._client.managed_cursor() as cursor:
                cursor.execute(sql, params)

    def batch_insert_invoices(
        self,
        records: Sequence[tuple[str, str, RawInvoicePayload | dict[str, Any]]],
        paramstyle: str | None = None,
    ) -> int:
        """Persist multiple invoice payloads into Snowflake Bronze table.

        Args:
            records: Sequence of (source_file, partner_id, payload) tuples.
            paramstyle: Optional parameter placeholder style.

        Returns:
            int: Number of successfully inserted records.
        """
        inserted_count = 0
        sql = get_insert_sql(paramstyle)

        def _do_batch(client: SnowflakeClient) -> int:
            nonlocal inserted_count
            with client.managed_cursor() as cursor:
                for source_file, partner_id, payload in records:
                    if isinstance(payload, RawInvoicePayload):
                        payload_json = payload.model_dump_json()
                    elif isinstance(payload, dict):
                        payload_json = json.dumps(payload, default=str)
                    else:
                        raise TypeError(f"Unsupported payload type: {type(payload)}")
                    cursor.execute(sql, (source_file, partner_id, payload_json))
                    inserted_count += 1
            return inserted_count

        if not self._client.is_connected:
            with self._client:
                return _do_batch(self._client)
        else:
            return _do_batch(self._client)

    def __enter__(self) -> "BronzeInvoiceRepository":
        """Enter context manager, establishing connection if not already open."""
        if not self._client.is_connected:
            self._client.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit context manager, releasing connection resources if owned."""
        if self._owns_connection:
            self._client.close()
