"""Open-Meteo REST API client for regional climatic metrics ingestion.

Fetches historical and forecasted meteorological data across configured distribution
hubs using httpx with tenacity exponential backoff and retry policies.
"""

import logging
from collections.abc import Sequence
from datetime import date, timedelta
from types import TracebackType
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.ingestion.config.hubs import DISTRIBUTION_HUBS, DistributionHub
from src.ingestion.models.multimodal import WeatherMetricRecord

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://archive-api.open-meteo.com/v1/archive"


class OpenMeteoClient:
    """Client for querying Open-Meteo historical and forecast weather APIs.

    Attributes:
        base_url: Base endpoint URL for Open-Meteo API.
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        client: httpx.Client | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 15.0,
        max_retries: int = 3,
    ) -> None:
        """Initialize Open-Meteo client.

        Args:
            client: Optional httpx.Client instance for connection pooling or test mocking.
            base_url: Base API URL. Defaults to Open-Meteo historical archive API.
            timeout: HTTP request timeout in seconds.
            max_retries: Maximum retry attempts for transient failures.
        """
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self._external_client = client
        self._client = client or httpx.Client(timeout=timeout)

    @property
    def http_client(self) -> httpx.Client:
        """Underlying HTTP client."""
        return self._client

    def _execute_request(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute HTTP GET request with tenacity retry policy.

        Args:
            params: Query parameters dictionary.

        Returns:
            dict[str, Any]: Parsed JSON response.

        Raises:
            httpx.HTTPStatusError: If server responds with 4xx or persistent 5xx.
            httpx.RequestError: If network connection drops persistently.
        """

        @retry(
            reraise=True,
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=5.0),
            retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        )
        def _get_with_retry() -> dict[str, Any]:
            response = self._client.get(self.base_url, params=params)
            response.raise_for_status()
            return response.json()

        return _get_with_retry()

    def fetch_hub_weather(
        self,
        hub: DistributionHub,
        start_date: date | str,
        end_date: date | str,
    ) -> list[WeatherMetricRecord]:
        """Fetch daily weather metrics for a single distribution hub.

        Args:
            hub: Target DistributionHub with coordinates and timezone.
            start_date: Beginning date of observation interval.
            end_date: Ending date of observation interval.

        Returns:
            list[WeatherMetricRecord]: Sequence of validated daily weather metric records.

        Raises:
            ValueError: If response payload structure is missing required daily series.
        """
        start_str = start_date.isoformat() if isinstance(start_date, date) else str(start_date)
        end_str = end_date.isoformat() if isinstance(end_date, date) else str(end_date)

        params: dict[str, Any] = {
            "latitude": hub.latitude,
            "longitude": hub.longitude,
            "start_date": start_str,
            "end_date": end_str,
            "daily": ["temperature_2m_max", "temperature_2m_min", "precipitation_sum"],
            "timezone": hub.timezone,
        }

        logger.info(
            "Querying Open-Meteo for hub %s (%s, %s) from %s to %s",
            hub.hub_id,
            hub.city,
            hub.state,
            start_str,
            end_str,
        )

        data = self._execute_request(params)

        if "daily" not in data:
            raise ValueError(f"Open-Meteo response missing 'daily' section: {data}")

        daily = data["daily"]
        dates: list[str] = daily.get("time", [])
        temp_max_list: list[float] = daily.get("temperature_2m_max", [])
        temp_min_list: list[float] = daily.get("temperature_2m_min", [])
        precipitation_list: list[float] = daily.get("precipitation_sum", [])

        if not (len(dates) == len(temp_max_list) == len(temp_min_list) == len(precipitation_list)):
            raise ValueError("Mismatched array lengths in Open-Meteo daily metrics response")

        records: list[WeatherMetricRecord] = []
        for d_str, t_max, t_min, precip in zip(
            dates, temp_max_list, temp_min_list, precipitation_list, strict=True
        ):
            if t_max is None or t_min is None or precip is None:
                continue
            record_date = date.fromisoformat(d_str)
            records.append(
                WeatherMetricRecord(
                    city_hub=hub.city,
                    state=hub.state,
                    date=record_date,
                    temp_max=float(t_max),
                    temp_min=float(t_min),
                    precipitation_sum=max(0.0, float(precip)),
                )
            )

        logger.info("Retrieved %d weather metric records for hub %s", len(records), hub.hub_id)
        return records

    def fetch_all_hubs_weather(
        self,
        hubs: Sequence[DistributionHub] | None = None,
        start_date: date | str | None = None,
        end_date: date | str | None = None,
    ) -> list[WeatherMetricRecord]:
        """Iterate across all configured distribution hubs and collect weather records.

        Args:
            hubs: Optional sequence of DistributionHubs. Defaults to all registered hubs.
            start_date: Start date. Defaults to 7 days before end_date.
            end_date: End date. Defaults to yesterday.

        Returns:
            list[WeatherMetricRecord]: Combined weather metric records across all hubs.
        """
        target_hubs = hubs if hubs is not None else DISTRIBUTION_HUBS

        if end_date is None:
            resolved_end = date.today() - timedelta(days=1)
        elif isinstance(end_date, str):
            resolved_end = date.fromisoformat(end_date)
        else:
            resolved_end = end_date

        if start_date is None:
            resolved_start = resolved_end - timedelta(days=7)
        elif isinstance(start_date, str):
            resolved_start = date.fromisoformat(start_date)
        else:
            resolved_start = start_date

        all_records: list[WeatherMetricRecord] = []
        for hub in target_hubs:
            try:
                hub_records = self.fetch_hub_weather(
                    hub=hub,
                    start_date=resolved_start,
                    end_date=resolved_end,
                )
                all_records.extend(hub_records)
            except Exception as exc:
                logger.error("Failed to collect weather for hub %s: %s", hub.hub_id, exc)
                raise

        return all_records

    def __enter__(self) -> "OpenMeteoClient":
        """Enter context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit context manager, closing internal HTTP client if owned."""
        if self._external_client is None:
            self._client.close()
