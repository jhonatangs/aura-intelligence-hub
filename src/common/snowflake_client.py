"""Snowflake client module with RSA key-pair authentication.

Implements an enterprise-grade Snowflake connection client utilizing PKCS#8
private key deserialization, DER encoding, and Python context manager protocols.
"""

from collections.abc import Generator, Sequence
from contextlib import contextmanager
from pathlib import Path
from types import TracebackType
from typing import Any

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from snowflake.connector import SnowflakeConnection, connect
from snowflake.connector.cursor import SnowflakeCursor

from common.config import SnowflakeSettings, get_settings


def load_private_key(private_key_path: Path, passphrase: str | None = None) -> bytes:
    """Deserialize a PKCS#8 PEM private key and convert it to unencrypted DER bytes.

    Args:
        private_key_path: Filesystem path to the PKCS#8 PEM private key file.
        passphrase: Optional passphrase if the private key file is encrypted.

    Returns:
        bytes: Private key bytes serialized in DER format.

    Raises:
        FileNotFoundError: If the specified private key path does not exist.
        ValueError: If key deserialization fails or the passphrase is invalid.
    """
    key_bytes = private_key_path.read_bytes()
    password_bytes = passphrase.encode("utf-8") if passphrase else None

    private_key = serialization.load_pem_private_key(
        key_bytes,
        password=password_bytes,
        backend=default_backend(),
    )

    return private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


class SnowflakeClient:
    """Enterprise Snowflake client supporting RSA key-pair authentication and context management.

    Attributes:
        settings: SnowflakeSettings instance containing connection parameters.
    """

    def __init__(self, settings: SnowflakeSettings | None = None) -> None:
        """Initialize the Snowflake client.

        Args:
            settings: Optional SnowflakeSettings instance. Defaults to get_settings().
        """
        self._settings = settings or get_settings()
        self._conn: SnowflakeConnection | None = None

    @property
    def settings(self) -> SnowflakeSettings:
        """Active SnowflakeSettings instance."""
        return self._settings

    @property
    def connection(self) -> SnowflakeConnection:
        """Active Snowflake connection.

        Returns:
            SnowflakeConnection: The live Snowflake connection.

        Raises:
            RuntimeError: If connection has not been opened.
        """
        if self._conn is None:
            raise RuntimeError(
                "Snowflake connection is not open. Use within a context manager or call connect()."
            )
        return self._conn

    @property
    def is_connected(self) -> bool:
        """Check if an active connection is currently maintained."""
        return self._conn is not None

    def connect(self) -> SnowflakeConnection:
        """Establish connection to Snowflake using RSA key-pair authentication.

        Returns:
            SnowflakeConnection: The newly established Snowflake connection.
        """
        if self._conn is not None:
            return self._conn

        der_key_bytes = load_private_key(
            self._settings.snowflake_private_key_path,
            self._settings.snowflake_private_key_passphrase,
        )

        self._conn = connect(
            account=self._settings.snowflake_account,
            user=self._settings.snowflake_user,
            private_key=der_key_bytes,
            warehouse=self._settings.snowflake_warehouse,
            database=self._settings.snowflake_database,
            schema=self._settings.snowflake_schema,
            role=self._settings.snowflake_role,
        )
        return self._conn

    def close(self) -> None:
        """Close active Snowflake connection and clean up resources."""
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None

    def cursor(self) -> SnowflakeCursor:
        """Create and return a new Snowflake cursor from the active connection.

        Returns:
            SnowflakeCursor: Database cursor from the active connection.
        """
        return self.connection.cursor()

    @contextmanager
    def managed_cursor(self) -> Generator[SnowflakeCursor, None, None]:
        """Context manager for acquiring and safely releasing a Snowflake cursor.

        Yields:
            SnowflakeCursor: Database cursor.
        """
        cur = self.cursor()
        try:
            yield cur
        finally:
            cur.close()

    def execute_statement(
        self,
        statement: str,
        params: Sequence[Any] | dict[str, Any] | None = None,
    ) -> SnowflakeCursor:
        """Execute a single SQL statement using a managed cursor.

        Args:
            statement: SQL DDL/DML query string.
            params: Optional parameter sequence or dict for parameterized execution.

        Returns:
            SnowflakeCursor: The executed cursor.
        """
        cur = self.cursor()
        try:
            cur.execute(statement, params)
            return cur
        except Exception:
            cur.close()
            raise

    def __enter__(self) -> "SnowflakeClient":
        """Enter context manager, establishing Snowflake connection.

        Returns:
            SnowflakeClient: Active client instance.
        """
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit context manager, guaranteeing deterministic cleanup of connection."""
        self.close()
