"""Application configuration module using Pydantic Settings.

Provides immutable, strongly-typed configuration loading and validation
for Snowflake RSA key-pair authentication.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SnowflakeSettings(BaseSettings):
    """Immutable configuration model for Snowflake connectivity and authentication.

    Attributes:
        snowflake_account: Target Snowflake account identifier.
        snowflake_user: Snowflake username for authentication.
        snowflake_private_key_path: Path to the PKCS#8 RSA private key file.
        snowflake_private_key_passphrase: Optional passphrase for the private key.
        snowflake_role: Active Snowflake role.
        snowflake_warehouse: Target Snowflake virtual warehouse.
        snowflake_database: Target Snowflake database.
        snowflake_schema: Target Snowflake schema.
    """

    snowflake_account: str = Field(..., description="Snowflake account identifier")
    snowflake_user: str = Field(..., description="Snowflake username")
    snowflake_private_key_path: Path = Field(..., description="Path to PKCS#8 RSA private key file")
    snowflake_private_key_passphrase: str | None = Field(
        default=None, description="Passphrase for encrypted private key"
    )
    snowflake_role: str = Field(default="ACCOUNTADMIN", description="Snowflake role")
    snowflake_warehouse: str = Field(
        default="COMPUTE_WH", description="Snowflake virtual warehouse"
    )
    snowflake_database: str = Field(default="AURA_LAKEHOUSE", description="Snowflake database")
    snowflake_schema: str = Field(default="BRONZE", description="Snowflake schema")

    model_config = SettingsConfigDict(
        frozen=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator("snowflake_private_key_path")
    @classmethod
    def validate_private_key_path(cls, value: Path) -> Path:
        """Validate that the private key path exists and points to a regular file.

        Args:
            value: Path to the private key file.

        Returns:
            Path: Resolved absolute path to the private key file.

        Raises:
            ValueError: If the path does not exist or is not a file.
        """
        resolved_path = Path(value).expanduser().resolve()
        if not resolved_path.exists():
            raise ValueError(f"Private key file does not exist: {value}")
        if not resolved_path.is_file():
            raise ValueError(f"Private key path is not a file: {value}")
        return resolved_path

    @property
    def account(self) -> str:
        """Snowflake account identifier."""
        return self.snowflake_account

    @property
    def user(self) -> str:
        """Snowflake username."""
        return self.snowflake_user

    @property
    def private_key_path(self) -> Path:
        """Resolved path to the private key file."""
        return self.snowflake_private_key_path

    @property
    def private_key_passphrase(self) -> str | None:
        """Passphrase for the private key."""
        return self.snowflake_private_key_passphrase

    @property
    def role(self) -> str:
        """Active Snowflake role."""
        return self.snowflake_role

    @property
    def warehouse(self) -> str:
        """Target Snowflake virtual warehouse."""
        return self.snowflake_warehouse

    @property
    def database(self) -> str:
        """Target Snowflake database."""
        return self.snowflake_database

    @property
    def schema(self) -> str:
        """Target Snowflake schema."""
        return self.snowflake_schema


@lru_cache(maxsize=1)
def get_settings() -> SnowflakeSettings:
    """Load and return the cached application configuration.

    Returns:
        SnowflakeSettings: Immutable configuration instance.
    """
    return SnowflakeSettings()
