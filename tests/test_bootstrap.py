"""Unit tests for Snowflake bootstrapping logic."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.bootstrap_snowflake import bootstrap_snowflake, parse_sql_statements


def test_parse_sql_statements() -> None:
    """Verify parsing of SQL statements with comments and whitespace."""
    sql = """
    -- This is a comment
    CREATE DATABASE IF NOT EXISTS AURA_LAKEHOUSE;

    -- Another comment
    CREATE SCHEMA IF NOT EXISTS AURA_LAKEHOUSE.BRONZE;
    """
    statements = parse_sql_statements(sql)
    assert len(statements) == 2
    assert statements[0] == "CREATE DATABASE IF NOT EXISTS AURA_LAKEHOUSE"
    assert statements[1] == "CREATE SCHEMA IF NOT EXISTS AURA_LAKEHOUSE.BRONZE"


def test_bootstrap_snowflake_file_not_found(tmp_path: Path) -> None:
    """Verify FileNotFoundError is raised when SQL file is absent."""
    missing = tmp_path / "missing.sql"
    with pytest.raises(FileNotFoundError):
        bootstrap_snowflake(missing)


def test_bootstrap_snowflake_execution(tmp_path: Path) -> None:
    """Verify sequential execution of SQL statements via SnowflakeClient."""
    sql_file = tmp_path / "init.sql"
    sql_file.write_text("CREATE DATABASE TEST_DB; CREATE SCHEMA TEST_SCHEMA;")

    mock_client = MagicMock()
    mock_cursor = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.managed_cursor.return_value.__enter__.return_value = mock_cursor

    with patch("scripts.bootstrap_snowflake.SnowflakeClient", return_value=mock_client):
        bootstrap_snowflake(sql_file)

    assert mock_cursor.execute.call_count == 2
    mock_cursor.execute.assert_any_call("CREATE DATABASE TEST_DB")
    mock_cursor.execute.assert_any_call("CREATE SCHEMA TEST_SCHEMA")
