"""Repository for persisting raw competitor pricing data into Snowflake Bronze layer.

Manages parameterized execution, JSON payload serialization, and metadata tracking
for AURA_LAKEHOUSE.BRONZE.COMPETITOR_PRICES_RAW.
"""

import json
from collections.abc import Sequence
from types import TracebackType
from typing import Any

import snowflake.connector

from src.common.snowflake_client import SnowflakeClient
from src.ingestion.models.multimodal import CompetitorPriceRecord


def get_competitor_insert_sql(paramstyle: str | None = None) -> str:
    """Return parameterized INSERT statement adapting to active connector paramstyle.

    Args:
        paramstyle: Optional explicit paramstyle ('qmark' or 'pyformat').

    Returns:
        str: Parameterized SQL statement.
    """
    style = paramstyle or getattr(snowflake.connector, "paramstyle", "pyformat")
    placeholder = "?" if style == "qmark" else "%s"
    return f"""INSERT INTO AURA_LAKEHOUSE.BRONZE.COMPETITOR_PRICES_RAW (
    source_url,
    competitor_brand,
    ingested_at,
    payload
) SELECT {placeholder}, {placeholder}, CURRENT_TIMESTAMP(), PARSE_JSON({placeholder})"""


class BronzeCompetitorPriceRepository:
    """Repository handling persistence of competitor prices into Snowflake Bronze storage.

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

    def insert_price_record(
        self,
        source_url: str,
        competitor_brand: str,
        payload: CompetitorPriceRecord | dict[str, Any],
        paramstyle: str | None = None,
    ) -> None:
        """Persist a single competitor price record into Snowflake Bronze.

        Args:
            source_url: Source website or URL identifier.
            competitor_brand: Brand identifier ('RED_BULL' or 'MONSTER').
            payload: Validated CompetitorPriceRecord or raw JSON-serializable dictionary.
            paramstyle: Optional parameter placeholder style.
        """
        if isinstance(payload, CompetitorPriceRecord):
            payload_json = payload.model_dump_json()
        elif isinstance(payload, dict):
            payload_json = json.dumps(payload, default=str)
        else:
            raise TypeError(f"Payload must be CompetitorPriceRecord or dict, got {type(payload)}")

        sql = get_competitor_insert_sql(paramstyle)
        params = (source_url, competitor_brand, payload_json)

        if not self._client.is_connected:
            with self._client:
                with self._client.managed_cursor() as cursor:
                    cursor.execute(sql, params)
        else:
            with self._client.managed_cursor() as cursor:
                cursor.execute(sql, params)

    def batch_insert_price_records(
        self,
        records: Sequence[tuple[str, str, CompetitorPriceRecord | dict[str, Any]]],
        paramstyle: str | None = None,
    ) -> int:
        """Persist multiple competitor price records into Snowflake Bronze table.

        Args:
            records: Sequence of (source_url, competitor_brand, payload) tuples.
            paramstyle: Optional parameter placeholder style.

        Returns:
            int: Number of successfully inserted records.
        """
        inserted_count = 0
        sql = get_competitor_insert_sql(paramstyle)

        def _do_batch(client: SnowflakeClient) -> int:
            nonlocal inserted_count
            with client.managed_cursor() as cursor:
                for source_url, competitor_brand, payload in records:
                    if isinstance(payload, CompetitorPriceRecord):
                        payload_json = payload.model_dump_json()
                    elif isinstance(payload, dict):
                        payload_json = json.dumps(payload, default=str)
                    else:
                        raise TypeError(f"Unsupported payload type: {type(payload)}")
                    cursor.execute(sql, (source_url, competitor_brand, payload_json))
                    inserted_count += 1
            return inserted_count

        if not self._client.is_connected:
            with self._client:
                return _do_batch(self._client)
        else:
            return _do_batch(self._client)

    def __enter__(self) -> "BronzeCompetitorPriceRepository":
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
