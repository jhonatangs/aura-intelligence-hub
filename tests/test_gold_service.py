"""Unit tests for Gold layer transformation service with mocked Snowflake client."""

from unittest.mock import MagicMock

import pytest

from src.transformation.services.gold_service import GoldTransformationService


@pytest.fixture
def mock_snowflake_client() -> MagicMock:
    """Fixture providing a mocked SnowflakeClient with cursor context manager."""
    client = MagicMock()
    cursor = MagicMock()
    cursor.rowcount = 10
    cursor.description = None
    client.is_connected = True
    client.managed_cursor.return_value.__enter__.return_value = cursor
    client.__enter__.return_value = client
    return client


def test_transform_dim_date_success(mock_snowflake_client: MagicMock) -> None:
    """Verify transform_dim_date executes single date merge query."""
    service = GoldTransformationService(client=mock_snowflake_client, database="TEST_DB")
    result = service.transform_dim_date()

    cursor = mock_snowflake_client.managed_cursor.return_value.__enter__.return_value
    assert cursor.execute.call_count == 1
    call_sql = cursor.execute.call_args[0][0]
    assert "MERGE INTO TEST_DB.GOLD.DIM_DATE" in call_sql
    assert result["status"] == "success"
    assert result["rows_affected"] == 10


def test_transform_dim_partners_success(mock_snowflake_client: MagicMock) -> None:
    """Verify transform_dim_partners executes partner merge query."""
    service = GoldTransformationService(client=mock_snowflake_client, database="TEST_DB")
    result = service.transform_dim_partners()

    cursor = mock_snowflake_client.managed_cursor.return_value.__enter__.return_value
    assert cursor.execute.call_count == 1
    call_sql = cursor.execute.call_args[0][0]
    assert "MERGE INTO TEST_DB.GOLD.DIM_PARTNERS" in call_sql
    assert result["status"] == "success"
    assert result["rows_affected"] == 10


def test_transform_dim_skus_success(mock_snowflake_client: MagicMock) -> None:
    """Verify transform_dim_skus executes SKU catalog merge query."""
    service = GoldTransformationService(client=mock_snowflake_client, database="TEST_DB")
    result = service.transform_dim_skus()

    cursor = mock_snowflake_client.managed_cursor.return_value.__enter__.return_value
    assert cursor.execute.call_count == 1
    call_sql = cursor.execute.call_args[0][0]
    assert "MERGE INTO TEST_DB.GOLD.DIM_SKUS" in call_sql
    assert result["status"] == "success"
    assert result["rows_affected"] == 10


def test_transform_dim_hubs_success(mock_snowflake_client: MagicMock) -> None:
    """Verify transform_dim_hubs executes distribution hubs merge query."""
    service = GoldTransformationService(client=mock_snowflake_client, database="TEST_DB")
    result = service.transform_dim_hubs()

    cursor = mock_snowflake_client.managed_cursor.return_value.__enter__.return_value
    assert cursor.execute.call_count == 1
    call_sql = cursor.execute.call_args[0][0]
    assert "MERGE INTO TEST_DB.GOLD.DIM_HUBS" in call_sql
    assert result["status"] == "success"
    assert result["rows_affected"] == 10


def test_transform_dimensions_success(mock_snowflake_client: MagicMock) -> None:
    """Verify transform_dimensions executes all 4 dimension merges."""
    service = GoldTransformationService(client=mock_snowflake_client, database="TEST_DB")
    result = service.transform_dimensions()

    cursor = mock_snowflake_client.managed_cursor.return_value.__enter__.return_value
    assert cursor.execute.call_count == 4
    assert result["status"] == "success"
    assert result["total_rows_affected"] == 40
    assert "dim_date" in result["dimensions"]
    assert "dim_partners" in result["dimensions"]
    assert "dim_skus" in result["dimensions"]
    assert "dim_hubs" in result["dimensions"]


def test_transform_fact_sellout_success(mock_snowflake_client: MagicMock) -> None:
    """Verify transform_fact_sellout executes sellout merge query."""
    service = GoldTransformationService(client=mock_snowflake_client, database="TEST_DB")
    result = service.transform_fact_sellout()

    cursor = mock_snowflake_client.managed_cursor.return_value.__enter__.return_value
    assert cursor.execute.call_count == 1
    call_sql = cursor.execute.call_args[0][0]
    assert "MERGE INTO TEST_DB.GOLD.FACT_SELLOUT" in call_sql
    assert result["status"] == "success"
    assert result["rows_affected"] == 10


def test_transform_fact_inventory_snapshot_success(mock_snowflake_client: MagicMock) -> None:
    """Verify transform_fact_inventory_snapshot executes inventory snapshot merge."""
    service = GoldTransformationService(client=mock_snowflake_client, database="TEST_DB")
    result = service.transform_fact_inventory_snapshot()

    cursor = mock_snowflake_client.managed_cursor.return_value.__enter__.return_value
    assert cursor.execute.call_count == 1
    call_sql = cursor.execute.call_args[0][0]
    assert "MERGE INTO TEST_DB.GOLD.FACT_INVENTORY_SNAPSHOT" in call_sql
    assert result["status"] == "success"
    assert result["rows_affected"] == 10


def test_transform_fact_competitor_pricing_success(mock_snowflake_client: MagicMock) -> None:
    """Verify transform_fact_competitor_pricing executes competitor pricing merge."""
    service = GoldTransformationService(client=mock_snowflake_client, database="TEST_DB")
    result = service.transform_fact_competitor_pricing()

    cursor = mock_snowflake_client.managed_cursor.return_value.__enter__.return_value
    assert cursor.execute.call_count == 1
    call_sql = cursor.execute.call_args[0][0]
    assert "MERGE INTO TEST_DB.GOLD.FACT_COMPETITOR_PRICING" in call_sql
    assert result["status"] == "success"
    assert result["rows_affected"] == 10


def test_transform_facts_success(mock_snowflake_client: MagicMock) -> None:
    """Verify transform_facts executes all 3 fact merges."""
    service = GoldTransformationService(client=mock_snowflake_client, database="TEST_DB")
    result = service.transform_facts()

    cursor = mock_snowflake_client.managed_cursor.return_value.__enter__.return_value
    assert cursor.execute.call_count == 3
    assert result["status"] == "success"
    assert result["total_rows_affected"] == 30
    assert "fact_sellout" in result["facts"]
    assert "fact_inventory_snapshot" in result["facts"]
    assert "fact_competitor_pricing" in result["facts"]


def test_transform_all_success(mock_snowflake_client: MagicMock) -> None:
    """Verify transform_all executes dimensions then facts in topological sequence."""
    service = GoldTransformationService(client=mock_snowflake_client, database="TEST_DB")
    result = service.transform_all()

    cursor = mock_snowflake_client.managed_cursor.return_value.__enter__.return_value
    # 4 dimensions + 3 facts = 7 executes
    assert cursor.execute.call_count == 7
    assert result["status"] == "success"
    assert result["total_rows_affected"] == 70
    assert "dimensions" in result
    assert "facts" in result


def test_rollback_on_query_failure(mock_snowflake_client: MagicMock) -> None:
    """Verify ROLLBACK execution when query fails."""
    cursor = mock_snowflake_client.managed_cursor.return_value.__enter__.return_value
    cursor.execute.side_effect = RuntimeError("Snowflake syntax error")

    service = GoldTransformationService(client=mock_snowflake_client, database="TEST_DB")

    with pytest.raises(RuntimeError, match="Snowflake syntax error"):
        service.transform_dim_date()

    cursor.execute.assert_any_call("ROLLBACK")


def test_context_manager_lifecycle() -> None:
    """Verify context manager enters and exits cleanly."""
    mock_client = MagicMock()
    mock_client.is_connected = False

    service = GoldTransformationService(client=mock_client)
    with service:
        mock_client.connect.assert_called_once()

    mock_client.close.assert_not_called()
