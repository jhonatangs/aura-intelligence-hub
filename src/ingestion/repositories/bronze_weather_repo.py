"""Repository for landing raw Open-Meteo weather metrics into Snowflake Bronze layer.

Manages parameterized execution, JSON payload serialization, and metadata tracking
for AURA_LAKEHOUSE.BRONZE.WEATHER_METRICS_RAW.
"""

import json
from collections.abc import Sequence
from types import TracebackType
from typing import Any

import snowflake.connector

from src.common.snowflake_client import SnowflakeClient
from src.ingestion.models.multimodal import WeatherMetricRecord


def get_weather_insert_sql(paramstyle: str | None = None) -> str:
    """Return parameterized INSERT statement adapting to active connector paramstyle.

    Args:
        paramstyle: Optional explicit paramstyle ('qmark' or 'pyformat').

    Returns:
        str: Parameterized SQL statement.
    """
    style = paramstyle or getattr(snowflake.connector, "paramstyle", "pyformat")
    placeholder = "?" if style == "qmark" else "%s"
    return f"""INSERT INTO AURA_LAKEHOUSE.BRONZE.WEATHER_METRICS_RAW (
    city_hub,
    state,
    ingested_at,
    payload
) SELECT {placeholder}, {placeholder}, CURRENT_TIMESTAMP(), PARSE_JSON({placeholder})"""


class BronzeWeatherRepository:
    """Repository handling persistence of raw weather metrics into Snowflake Bronze storage.

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

    def insert_weather_record(
        self,
        city_hub: str,
        state: str,
        payload: WeatherMetricRecord | dict[str, Any],
        paramstyle: str | None = None,
    ) -> None:
        """Persist a single weather metric record into Snowflake Bronze.

        Args:
            city_hub: Distribution hub city name.
            state: Two-letter state code.
            payload: Validated WeatherMetricRecord or raw JSON-serializable dictionary.
            paramstyle: Optional parameter placeholder style.
        """
        if isinstance(payload, WeatherMetricRecord):
            payload_json = payload.model_dump_json()
        elif isinstance(payload, dict):
            payload_json = json.dumps(payload, default=str)
        else:
            raise TypeError(f"Payload must be WeatherMetricRecord or dict, got {type(payload)}")

        sql = get_weather_insert_sql(paramstyle)
        params = (city_hub, state, payload_json)

        if not self._client.is_connected:
            with self._client:
                with self._client.managed_cursor() as cursor:
                    cursor.execute(sql, params)
        else:
            with self._client.managed_cursor() as cursor:
                cursor.execute(sql, params)

    def batch_insert_weather_records(
        self,
        records: Sequence[tuple[str, str, WeatherMetricRecord | dict[str, Any]]],
        paramstyle: str | None = None,
    ) -> int:
        """Persist multiple weather records into Snowflake Bronze table.

        Args:
            records: Sequence of (city_hub, state, payload) tuples.
            paramstyle: Optional parameter placeholder style.

        Returns:
            int: Number of successfully inserted records.
        """
        inserted_count = 0
        sql = get_weather_insert_sql(paramstyle)

        def _do_batch(client: SnowflakeClient) -> int:
            nonlocal inserted_count
            with client.managed_cursor() as cursor:
                for city_hub, state, payload in records:
                    if isinstance(payload, WeatherMetricRecord):
                        payload_json = payload.model_dump_json()
                    elif isinstance(payload, dict):
                        payload_json = json.dumps(payload, default=str)
                    else:
                        raise TypeError(f"Unsupported payload type: {type(payload)}")
                    cursor.execute(sql, (city_hub, state, payload_json))
                    inserted_count += 1
            return inserted_count

        if not self._client.is_connected:
            with self._client:
                return _do_batch(self._client)
        else:
            return _do_batch(self._client)

    def __enter__(self) -> "BronzeWeatherRepository":
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
