"""Unit tests for Open-Meteo climatic API client."""

from datetime import date
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.ingestion.clients.weather_client import OpenMeteoClient
from src.ingestion.config.hubs import DISTRIBUTION_HUBS, DistributionHub


@pytest.fixture
def sample_hub() -> DistributionHub:
    """Fixture returning sample São Paulo hub."""
    return DistributionHub(
        hub_id="HUB-SP",
        name="São Paulo Central Hub",
        city="São Paulo",
        state="SP",
        latitude=-23.5505,
        longitude=-46.6333,
        timezone="America/Sao_Paulo",
    )


@pytest.fixture
def mock_open_meteo_payload() -> dict:
    """Fixture returning standard Open-Meteo JSON response payload."""
    return {
        "latitude": -23.55,
        "longitude": -46.63,
        "daily": {
            "time": ["2026-03-01", "2026-03-02"],
            "temperature_2m_max": [31.5, 29.8],
            "temperature_2m_min": [20.1, 19.4],
            "precipitation_sum": [0.0, 12.5],
        },
    }


def test_fetch_hub_weather_success(
    sample_hub: DistributionHub, mock_open_meteo_payload: dict
) -> None:
    """Verify successful weather metrics retrieval and Pydantic record mapping."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_open_meteo_payload
    mock_response.raise_for_status.return_value = None

    mock_http_client = MagicMock(spec=httpx.Client)
    mock_http_client.get.return_value = mock_response

    client = OpenMeteoClient(client=mock_http_client)
    records = client.fetch_hub_weather(sample_hub, start_date="2026-03-01", end_date="2026-03-02")

    assert len(records) == 2
    rec1, rec2 = records
    assert rec1.city_hub == "São Paulo"
    assert rec1.state == "SP"
    assert rec1.date == date(2026, 3, 1)
    assert rec1.temp_max == 31.5
    assert rec1.temp_min == 20.1
    assert rec1.precipitation_sum == 0.0

    assert rec2.date == date(2026, 3, 2)
    assert rec2.precipitation_sum == 12.5


def test_fetch_all_hubs_weather(mock_open_meteo_payload: dict) -> None:
    """Verify iteration across multiple hubs."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_open_meteo_payload
    mock_response.raise_for_status.return_value = None

    mock_http_client = MagicMock(spec=httpx.Client)
    mock_http_client.get.return_value = mock_response

    client = OpenMeteoClient(client=mock_http_client)
    test_hubs = DISTRIBUTION_HUBS[:3]
    records = client.fetch_all_hubs_weather(
        hubs=test_hubs, start_date="2026-03-01", end_date="2026-03-02"
    )

    # 3 hubs * 2 daily records each = 6 records
    assert len(records) == 6
    assert mock_http_client.get.call_count == 3


def test_weather_client_retry_on_http_5xx(
    sample_hub: DistributionHub, mock_open_meteo_payload: dict
) -> None:
    """Verify tenacity retry recovers when initial call yields 500 error."""
    mock_err_response = MagicMock(spec=httpx.Response)
    mock_err_response.status_code = 503
    mock_err_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Service Unavailable", request=MagicMock(), response=mock_err_response
    )

    mock_ok_response = MagicMock(spec=httpx.Response)
    mock_ok_response.status_code = 200
    mock_ok_response.json.return_value = mock_open_meteo_payload
    mock_ok_response.raise_for_status.return_value = None

    mock_http_client = MagicMock(spec=httpx.Client)
    mock_http_client.get.side_effect = [mock_err_response, mock_ok_response]

    client = OpenMeteoClient(client=mock_http_client, max_retries=3)
    records = client.fetch_hub_weather(sample_hub, start_date="2026-03-01", end_date="2026-03-02")

    assert len(records) == 2
    assert mock_http_client.get.call_count == 2


def test_weather_client_persistent_failure_raises(sample_hub: DistributionHub) -> None:
    """Verify exception is raised when all retries are exhausted."""
    mock_err_response = MagicMock(spec=httpx.Response)
    mock_err_response.status_code = 500
    mock_err_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Internal Server Error", request=MagicMock(), response=mock_err_response
    )

    mock_http_client = MagicMock(spec=httpx.Client)
    mock_http_client.get.return_value = mock_err_response

    client = OpenMeteoClient(client=mock_http_client, max_retries=2)
    with pytest.raises(httpx.HTTPStatusError):
        client.fetch_hub_weather(sample_hub, start_date="2026-03-01", end_date="2026-03-02")

    assert mock_http_client.get.call_count == 2


def test_weather_client_missing_daily_section(sample_hub: DistributionHub) -> None:
    """Verify ValueError is raised if 'daily' section is absent from payload."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"error": True, "reason": "Invalid coordinate"}
    mock_response.raise_for_status.return_value = None

    mock_http_client = MagicMock(spec=httpx.Client)
    mock_http_client.get.return_value = mock_response

    client = OpenMeteoClient(client=mock_http_client)
    with pytest.raises(ValueError, match="missing 'daily' section"):
        client.fetch_hub_weather(sample_hub, start_date="2026-03-01", end_date="2026-03-02")


def test_weather_client_mismatched_array_lengths(sample_hub: DistributionHub) -> None:
    """Verify ValueError is raised if daily metric arrays have unequal lengths."""
    payload = {
        "daily": {
            "time": ["2026-03-01", "2026-03-02"],
            "temperature_2m_max": [30.0],  # only 1 element
            "temperature_2m_min": [20.0, 19.0],
            "precipitation_sum": [0.0, 0.0],
        }
    }
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = payload
    mock_response.raise_for_status.return_value = None

    mock_http_client = MagicMock(spec=httpx.Client)
    mock_http_client.get.return_value = mock_response

    client = OpenMeteoClient(client=mock_http_client)
    with pytest.raises(ValueError, match="Mismatched array lengths"):
        client.fetch_hub_weather(sample_hub, start_date="2026-03-01", end_date="2026-03-02")


def test_weather_client_context_manager_lifecycle() -> None:
    """Verify internal client is closed on context manager exit."""
    mock_http_client = MagicMock(spec=httpx.Client)
    with patch("src.ingestion.clients.weather_client.httpx.Client", return_value=mock_http_client):
        with OpenMeteoClient() as client:
            assert client.http_client is mock_http_client
        mock_http_client.close.assert_called_once()
