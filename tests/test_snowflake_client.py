"""Unit tests for SnowflakeClient and key-pair authentication.

Verifies private key deserialization, DER encoding, connection parameter passing,
cursor lifecycle, and deterministic resource cleanup under normal and error conditions.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from cryptography.hazmat.primitives import serialization

from common.config import SnowflakeSettings
from common.snowflake_client import SnowflakeClient, load_private_key


@pytest.fixture
def mock_settings(tmp_path: Path) -> SnowflakeSettings:
    """Fixture providing a valid SnowflakeSettings instance with a temporary key file."""
    key_file = tmp_path / "mock_key.p8"
    key_file.write_bytes(
        b"-----BEGIN ENCRYPTED PRIVATE KEY-----\nMOCK\n-----END ENCRYPTED PRIVATE KEY-----"
    )

    return SnowflakeSettings(
        snowflake_account="test-aura-account",
        snowflake_user="AURA_BOT",
        snowflake_private_key_path=key_file,
        snowflake_private_key_passphrase="mock_passphrase",
        snowflake_role="SYSADMIN",
        snowflake_warehouse="COMPUTE_WH",
        snowflake_database="AURA_LAKEHOUSE",
        snowflake_schema="BRONZE",
    )


def test_load_private_key_der_serialization(tmp_path: Path) -> None:
    """Verify that load_private_key converts PEM key to unencrypted DER bytes."""
    key_file = tmp_path / "test.p8"
    key_file.write_bytes(b"DUMMY_PEM_BYTES")

    mock_key = MagicMock()
    mock_key.private_bytes.return_value = b"EXPECTED_DER_BYTES"

    with patch(
        "common.snowflake_client.serialization.load_pem_private_key",
        return_value=mock_key,
    ) as mock_loader:
        der_bytes = load_private_key(key_file, passphrase="my_password")

    mock_loader.assert_called_once()
    call_args = mock_loader.call_args
    assert call_args[0][0] == b"DUMMY_PEM_BYTES"
    assert call_args[1]["password"] == b"my_password"

    mock_key.private_bytes.assert_called_once()
    call_kwargs = mock_key.private_bytes.call_args[1]
    assert call_kwargs["encoding"] == serialization.Encoding.DER
    assert call_kwargs["format"] == serialization.PrivateFormat.PKCS8
    assert isinstance(call_kwargs["encryption_algorithm"], serialization.NoEncryption)
    assert der_bytes == b"EXPECTED_DER_BYTES"


def test_load_private_key_no_passphrase(tmp_path: Path) -> None:
    """Verify password argument is None when no passphrase is provided."""
    key_file = tmp_path / "unencrypted.p8"
    key_file.write_bytes(b"UNENCRYPTED_PEM")

    mock_key = MagicMock()
    mock_key.private_bytes.return_value = b"DER_BYTES"

    with patch(
        "common.snowflake_client.serialization.load_pem_private_key",
        return_value=mock_key,
    ) as mock_loader:
        der_bytes = load_private_key(key_file, passphrase=None)

    assert mock_loader.call_args[1]["password"] is None
    assert der_bytes == b"DER_BYTES"


def test_snowflake_client_connection_parameters(mock_settings: SnowflakeSettings) -> None:
    """Verify Snowflake connection parameters and idempotency of connect()."""
    mock_conn = MagicMock()

    with (
        patch(
            "common.snowflake_client.load_private_key", return_value=b"MOCK_DER_KEY"
        ) as mock_load_key,
        patch("common.snowflake_client.connect", return_value=mock_conn) as mock_sf_connect,
    ):
        client = SnowflakeClient(settings=mock_settings)
        conn = client.connect()

        mock_load_key.assert_called_once_with(
            mock_settings.snowflake_private_key_path,
            mock_settings.snowflake_private_key_passphrase,
        )
        mock_sf_connect.assert_called_once_with(
            account="test-aura-account",
            user="AURA_BOT",
            private_key=b"MOCK_DER_KEY",
            warehouse="COMPUTE_WH",
            database="AURA_LAKEHOUSE",
            schema="BRONZE",
            role="SYSADMIN",
        )
        assert conn == mock_conn
        assert client.is_connected

        # Idempotency check: second connect() must not re-open connection
        conn2 = client.connect()
        assert conn2 == mock_conn
        mock_sf_connect.assert_called_once()


def test_snowflake_client_context_manager_lifecycle(mock_settings: SnowflakeSettings) -> None:
    """Verify context manager enters by connecting and exits by closing."""
    mock_conn = MagicMock()

    with (
        patch("common.snowflake_client.load_private_key", return_value=b"DER_KEY"),
        patch("common.snowflake_client.connect", return_value=mock_conn),
    ):
        client = SnowflakeClient(settings=mock_settings)
        assert not client.is_connected

        with client as active_client:
            assert active_client is client
            assert active_client.is_connected
            assert active_client.connection == mock_conn

        assert not client.is_connected
        mock_conn.close.assert_called_once()


def test_snowflake_client_cursor_lifecycle(mock_settings: SnowflakeSettings) -> None:
    """Verify cursor creation and managed cursor lifecycle."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with (
        patch("common.snowflake_client.load_private_key", return_value=b"DER_KEY"),
        patch("common.snowflake_client.connect", return_value=mock_conn),
    ):
        with SnowflakeClient(settings=mock_settings) as client:
            # Direct cursor acquisition
            cur = client.cursor()
            assert cur == mock_cursor

            # Managed cursor context
            with client.managed_cursor() as m_cur:
                assert m_cur == mock_cursor
            mock_cursor.close.assert_called_once()

            # Execute statement
            client.execute_statement("SELECT 1")
            mock_cursor.execute.assert_called_with("SELECT 1", None)


def test_snowflake_client_deterministic_cleanup_on_error(mock_settings: SnowflakeSettings) -> None:
    """Verify deterministic connection closure when an exception occurs inside context."""
    mock_conn = MagicMock()

    with (
        patch("common.snowflake_client.load_private_key", return_value=b"DER_KEY"),
        patch("common.snowflake_client.connect", return_value=mock_conn),
    ):
        client = SnowflakeClient(settings=mock_settings)

        with pytest.raises(RuntimeError, match="Pipeline query failure"):
            with client:
                raise RuntimeError("Pipeline query failure")

        assert not client.is_connected
        mock_conn.close.assert_called_once()


def test_unconnected_client_raises_on_connection_access(mock_settings: SnowflakeSettings) -> None:
    """Verify RuntimeError is raised when accessing connection before connect()."""
    client = SnowflakeClient(settings=mock_settings)
    assert not client.is_connected

    with pytest.raises(RuntimeError, match="Snowflake connection is not open"):
        _ = client.connection
