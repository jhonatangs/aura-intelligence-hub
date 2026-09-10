"""Unit tests for Dagster Asset Checks and Data Quality Verifications.

Validates query logic and Dagster AssetCheckResult evaluations for surrogate keys,
revenue positivity, inventory non-negativity, and competitor price bounds against
mocked Snowflake cursors and invalid datasets.
"""

from unittest.mock import MagicMock, patch

from dagster import build_asset_check_context

from src.orchestration.checks.quality_checks import (
    check_competitor_price_bounds,
    check_inventory_non_negative_balances,
    check_sellout_positive_revenue,
    check_sellout_surrogate_keys_not_null,
    query_competitor_invalid_price_bounds,
    query_inventory_negative_balances,
    query_sellout_negative_revenue,
    query_sellout_null_surrogate_keys,
)

CLIENT_PATCH = "src.orchestration.checks.quality_checks.SnowflakeClient"


# -----------------------------------------------------------------------------
# Query Helper Tests
# -----------------------------------------------------------------------------


def test_query_sellout_null_surrogate_keys_zero_violations() -> None:
    """Verify query returns 0 when all surrogate keys are present."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (0,)

    result = query_sellout_null_surrogate_keys(mock_cursor, database="TEST_DB")
    assert result == 0
    sql = mock_cursor.execute.call_args[0][0]
    assert "TEST_DB.GOLD.FACT_SELLOUT" in sql
    assert "partner_key IS NULL" in sql


def test_query_sellout_null_surrogate_keys_with_violations() -> None:
    """Verify query returns violation count when null keys are detected."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (7,)

    result = query_sellout_null_surrogate_keys(mock_cursor, database="TEST_DB")
    assert result == 7


def test_query_sellout_null_surrogate_keys_none_row() -> None:
    """Verify query returns 0 when cursor fetchone returns None."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None

    result = query_sellout_null_surrogate_keys(mock_cursor, database="TEST_DB")
    assert result == 0


def test_query_sellout_negative_revenue_zero_violations() -> None:
    """Verify query returns 0 when revenues are all positive."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (0,)

    result = query_sellout_negative_revenue(mock_cursor, database="TEST_DB")
    assert result == 0
    sql = mock_cursor.execute.call_args[0][0]
    assert "total_price < 0" in sql


def test_query_sellout_negative_revenue_with_violations() -> None:
    """Verify query returns count when negative revenues exist."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (3,)

    result = query_sellout_negative_revenue(mock_cursor, database="TEST_DB")
    assert result == 3


def test_query_inventory_negative_balances_zero_violations() -> None:
    """Verify query returns 0 when stock balances are non-negative."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (0,)

    result = query_inventory_negative_balances(mock_cursor, database="TEST_DB")
    assert result == 0
    sql = mock_cursor.execute.call_args[0][0]
    assert "stock_quantity < 0" in sql


def test_query_inventory_negative_balances_with_violations() -> None:
    """Verify query returns count when negative stock quantities exist."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (12,)

    result = query_inventory_negative_balances(mock_cursor, database="TEST_DB")
    assert result == 12


def test_query_competitor_invalid_price_bounds_zero_violations() -> None:
    """Verify query returns 0 when competitor price per ml is positive."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (0,)

    result = query_competitor_invalid_price_bounds(mock_cursor, database="TEST_DB")
    assert result == 0
    sql = mock_cursor.execute.call_args[0][0]
    assert "price_per_ml <= 0" in sql


def test_query_competitor_invalid_price_bounds_with_violations() -> None:
    """Verify query returns count when invalid price per ml exists."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (5,)

    result = query_competitor_invalid_price_bounds(mock_cursor, database="TEST_DB")
    assert result == 5


# -----------------------------------------------------------------------------
# Asset Check Execution Tests
# -----------------------------------------------------------------------------


def test_check_sellout_surrogate_keys_not_null_passed() -> None:
    """Verify check passes and emits correct metadata when zero null keys exist."""
    context = build_asset_check_context()
    mock_client = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (0,)
    mock_client.get_cursor.return_value.__enter__.return_value = mock_cursor

    with patch(CLIENT_PATCH, return_value=mock_client):
        result = check_sellout_surrogate_keys_not_null(context)

    assert result.passed is True
    assert result.metadata["violations"].value == 0
    assert "FACT_SELLOUT" in result.metadata["target_table"].value


def test_check_sellout_surrogate_keys_not_null_failed() -> None:
    """Verify check fails when NULL surrogate keys are discovered."""
    context = build_asset_check_context()
    mock_client = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (4,)
    mock_client.get_cursor.return_value.__enter__.return_value = mock_cursor

    with patch(CLIENT_PATCH, return_value=mock_client):
        result = check_sellout_surrogate_keys_not_null(context)

    assert result.passed is False
    assert result.metadata["violations"].value == 4
    assert "Found 4 row(s)" in result.description


def test_check_sellout_positive_revenue_passed() -> None:
    """Verify revenue positivity check passes on clean data."""
    context = build_asset_check_context()
    mock_client = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (0,)
    mock_client.get_cursor.return_value.__enter__.return_value = mock_cursor

    with patch(CLIENT_PATCH, return_value=mock_client):
        result = check_sellout_positive_revenue(context)

    assert result.passed is True
    assert result.metadata["violations"].value == 0


def test_check_sellout_positive_revenue_failed() -> None:
    """Verify revenue positivity check fails on negative numbers."""
    context = build_asset_check_context()
    mock_client = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (2,)
    mock_client.get_cursor.return_value.__enter__.return_value = mock_cursor

    with patch(CLIENT_PATCH, return_value=mock_client):
        result = check_sellout_positive_revenue(context)

    assert result.passed is False
    assert result.metadata["violations"].value == 2
    assert "negative revenue" in result.description


def test_check_inventory_non_negative_balances_passed() -> None:
    """Verify inventory non-negativity check passes on valid stock quantities."""
    context = build_asset_check_context()
    mock_client = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (0,)
    mock_client.get_cursor.return_value.__enter__.return_value = mock_cursor

    with patch(CLIENT_PATCH, return_value=mock_client):
        result = check_inventory_non_negative_balances(context)

    assert result.passed is True
    assert result.metadata["violations"].value == 0


def test_check_inventory_non_negative_balances_failed() -> None:
    """Verify inventory non-negativity check fails on negative balances."""
    context = build_asset_check_context()
    mock_client = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (9,)
    mock_client.get_cursor.return_value.__enter__.return_value = mock_cursor

    with patch(CLIENT_PATCH, return_value=mock_client):
        result = check_inventory_non_negative_balances(context)

    assert result.passed is False
    assert result.metadata["violations"].value == 9
    assert "negative stock" in result.description


def test_check_competitor_price_bounds_passed() -> None:
    """Verify competitor pricing check passes when price_per_ml > 0."""
    context = build_asset_check_context()
    mock_client = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (0,)
    mock_client.get_cursor.return_value.__enter__.return_value = mock_cursor

    with patch(CLIENT_PATCH, return_value=mock_client):
        result = check_competitor_price_bounds(context)

    assert result.passed is True
    assert result.metadata["violations"].value == 0


def test_check_competitor_price_bounds_failed() -> None:
    """Verify competitor pricing check fails when price_per_ml <= 0."""
    context = build_asset_check_context()
    mock_client = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (1,)
    mock_client.get_cursor.return_value.__enter__.return_value = mock_cursor

    with patch(CLIENT_PATCH, return_value=mock_client):
        result = check_competitor_price_bounds(context)

    assert result.passed is False
    assert result.metadata["violations"].value == 1
    assert "violating price_per_ml > 0" in result.description
