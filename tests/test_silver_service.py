"""Unit tests for Silver layer transformation service with mocked Snowflake client."""

from unittest.mock import MagicMock

import pytest

from src.transformation.services.silver_service import SilverTransformationService


@pytest.fixture
def mock_snowflake_client() -> MagicMock:
    """Fixture providing a mocked SnowflakeClient with cursor context manager."""
    client = MagicMock()
    cursor = MagicMock()
    cursor.rowcount = 5
    cursor.description = None
    client.is_connected = True
    client.managed_cursor.return_value.__enter__.return_value = cursor
    client.__enter__.return_value = client
    return client


def test_transform_invoices_success(mock_snowflake_client: MagicMock) -> None:
    """Verify transform_invoices executes both header and line-item MERGE queries."""
    service = SilverTransformationService(client=mock_snowflake_client, database="TEST_DB")
    result = service.transform_invoices()

    cursor = mock_snowflake_client.managed_cursor.return_value.__enter__.return_value
    assert cursor.execute.call_count == 2

    first_call = cursor.execute.call_args_list[0][0][0]
    second_call = cursor.execute.call_args_list[1][0][0]
    assert "MERGE INTO TEST_DB.SILVER.INVOICES" in first_call
    assert "MERGE INTO TEST_DB.SILVER.INVOICE_ITEMS" in second_call

    assert result["status"] == "success"
    assert result["invoices_affected"] == 5
    assert result["invoice_items_affected"] == 5
    assert result["total_rows_affected"] == 10
    assert len(result["target_tables"]) == 2


def test_transform_invoices_header_standalone(mock_snowflake_client: MagicMock) -> None:
    """Verify transform_invoices_header executes single header MERGE query."""
    service = SilverTransformationService(client=mock_snowflake_client, database="TEST_DB")
    result = service.transform_invoices_header()

    cursor = mock_snowflake_client.managed_cursor.return_value.__enter__.return_value
    assert cursor.execute.call_count == 1
    call_sql = cursor.execute.call_args[0][0]
    assert "MERGE INTO TEST_DB.SILVER.INVOICES" in call_sql
    assert result["status"] == "success"
    assert result["rows_affected"] == 5


def test_transform_invoice_items_standalone(mock_snowflake_client: MagicMock) -> None:
    """Verify transform_invoice_items executes line items MERGE query."""
    service = SilverTransformationService(client=mock_snowflake_client, database="TEST_DB")
    result = service.transform_invoice_items()

    cursor = mock_snowflake_client.managed_cursor.return_value.__enter__.return_value
    assert cursor.execute.call_count == 1
    call_sql = cursor.execute.call_args[0][0]
    assert "MERGE INTO TEST_DB.SILVER.INVOICE_ITEMS" in call_sql
    assert result["status"] == "success"
    assert result["rows_affected"] == 5


def test_transform_competitor_prices_success(mock_snowflake_client: MagicMock) -> None:
    """Verify transform_competitor_prices executes merge query."""
    service = SilverTransformationService(client=mock_snowflake_client, database="TEST_DB")
    result = service.transform_competitor_prices()

    cursor = mock_snowflake_client.managed_cursor.return_value.__enter__.return_value
    assert cursor.execute.call_count == 1
    call_sql = cursor.execute.call_args[0][0]
    assert "MERGE INTO TEST_DB.SILVER.COMPETITOR_PRICES" in call_sql
    assert result["status"] == "success"
    assert result["rows_affected"] == 5


def test_transform_weather_metrics_success(mock_snowflake_client: MagicMock) -> None:
    """Verify transform_weather_metrics executes merge query."""
    service = SilverTransformationService(client=mock_snowflake_client, database="TEST_DB")
    result = service.transform_weather_metrics()

    cursor = mock_snowflake_client.managed_cursor.return_value.__enter__.return_value
    assert cursor.execute.call_count == 1
    call_sql = cursor.execute.call_args[0][0]
    assert "MERGE INTO TEST_DB.SILVER.WEATHER_METRICS" in call_sql
    assert result["status"] == "success"
    assert result["rows_affected"] == 5


def test_transform_partner_inventory_success(mock_snowflake_client: MagicMock) -> None:
    """Verify transform_partner_inventory executes merge query."""
    service = SilverTransformationService(client=mock_snowflake_client, database="TEST_DB")
    result = service.transform_partner_inventory()

    cursor = mock_snowflake_client.managed_cursor.return_value.__enter__.return_value
    assert cursor.execute.call_count == 1
    call_sql = cursor.execute.call_args[0][0]
    assert "MERGE INTO TEST_DB.SILVER.PARTNER_INVENTORY" in call_sql
    assert result["status"] == "success"
    assert result["rows_affected"] == 5


def test_transform_all_success(mock_snowflake_client: MagicMock) -> None:
    """Verify transform_all executes all transformations in topological order."""
    service = SilverTransformationService(client=mock_snowflake_client, database="TEST_DB")
    result = service.transform_all()

    cursor = mock_snowflake_client.managed_cursor.return_value.__enter__.return_value
    # 2 for invoices + 1 for competitor + 1 for weather + 1 for inventory = 5 executes
    assert cursor.execute.call_count == 5
    assert result["status"] == "success"
    assert result["total_rows_affected"] == 25
    assert "invoices" in result["datasets"]
    assert "competitor_prices" in result["datasets"]
    assert "weather_metrics" in result["datasets"]
    assert "partner_inventory" in result["datasets"]


def test_rollback_on_query_failure(mock_snowflake_client: MagicMock) -> None:
    """Verify ROLLBACK execution when query fails."""
    cursor = mock_snowflake_client.managed_cursor.return_value.__enter__.return_value
    cursor.execute.side_effect = RuntimeError("Snowflake query syntax error")

    service = SilverTransformationService(client=mock_snowflake_client, database="TEST_DB")

    with pytest.raises(RuntimeError, match="Snowflake query syntax error"):
        service.transform_weather_metrics()

    cursor.execute.assert_any_call("ROLLBACK")


def test_context_manager_lifecycle() -> None:
    """Verify context manager enters and exits cleanly."""
    mock_client = MagicMock()
    mock_client.is_connected = False

    service = SilverTransformationService(client=mock_client)
    with service:
        mock_client.connect.assert_called_once()

    # Client was passed in, so service does not close it (owns_connection = False)
    mock_client.close.assert_not_called()
