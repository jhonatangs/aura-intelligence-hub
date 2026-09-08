"""Unit tests for SnowflakeSettings configuration model.

Validates environment parameter loading, immutability, path existence validation,
and rejection of invalid private key paths.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from common.config import SnowflakeSettings


@pytest.fixture(autouse=True)
def isolate_from_local_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Isolate unit tests from the workspace .env file by changing working directory."""
    monkeypatch.chdir(tmp_path)


def test_config_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test successful configuration loading from environment variables."""
    key_file = tmp_path / "test_key.p8"
    key_file.write_text("dummy private key content")

    monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "org-account-test")
    monkeypatch.setenv("SNOWFLAKE_USER", "AURA_TEST_USER")
    monkeypatch.setenv("SNOWFLAKE_PRIVATE_KEY_PATH", str(key_file))
    monkeypatch.setenv("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE", "secret123")
    monkeypatch.setenv("SNOWFLAKE_ROLE", "AURA_ANALYST")
    monkeypatch.setenv("SNOWFLAKE_WAREHOUSE", "ANALYTICS_WH")
    monkeypatch.setenv("SNOWFLAKE_DATABASE", "AURA_DEV")
    monkeypatch.setenv("SNOWFLAKE_SCHEMA", "SILVER")

    settings = SnowflakeSettings()

    assert settings.account == "org-account-test"
    assert settings.user == "AURA_TEST_USER"
    assert settings.private_key_path == key_file.resolve()
    assert settings.private_key_passphrase == "secret123"
    assert settings.role == "AURA_ANALYST"
    assert settings.warehouse == "ANALYTICS_WH"
    assert settings.database == "AURA_DEV"
    assert settings.schema == "SILVER"


def test_config_default_values(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test default values for optional settings."""
    key_file = tmp_path / "default_key.p8"
    key_file.write_text("dummy")

    monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "test-account")
    monkeypatch.setenv("SNOWFLAKE_USER", "test-user")
    monkeypatch.setenv("SNOWFLAKE_PRIVATE_KEY_PATH", str(key_file))
    monkeypatch.delenv("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE", raising=False)
    monkeypatch.delenv("SNOWFLAKE_ROLE", raising=False)
    monkeypatch.delenv("SNOWFLAKE_WAREHOUSE", raising=False)
    monkeypatch.delenv("SNOWFLAKE_DATABASE", raising=False)
    monkeypatch.delenv("SNOWFLAKE_SCHEMA", raising=False)

    settings = SnowflakeSettings()

    assert settings.role == "ACCOUNTADMIN"
    assert settings.warehouse == "COMPUTE_WH"
    assert settings.database == "AURA_LAKEHOUSE"
    assert settings.schema == "BRONZE"
    assert settings.private_key_passphrase is None


def test_config_missing_private_key_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test validation failure when the private key file does not exist."""
    nonexistent = tmp_path / "does_not_exist.p8"

    monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "test-account")
    monkeypatch.setenv("SNOWFLAKE_USER", "test-user")
    monkeypatch.setenv("SNOWFLAKE_PRIVATE_KEY_PATH", str(nonexistent))

    with pytest.raises(ValidationError) as exc_info:
        SnowflakeSettings()

    assert "Private key file does not exist" in str(exc_info.value)


def test_config_directory_as_private_key_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test validation failure when the private key path is a directory."""
    directory_path = tmp_path / "not_a_file_dir"
    directory_path.mkdir()

    monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "test-account")
    monkeypatch.setenv("SNOWFLAKE_USER", "test-user")
    monkeypatch.setenv("SNOWFLAKE_PRIVATE_KEY_PATH", str(directory_path))

    with pytest.raises(ValidationError) as exc_info:
        SnowflakeSettings()

    assert "Private key path is not a file" in str(exc_info.value)


def test_config_immutability(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test that SnowflakeSettings is immutable (frozen=True)."""
    key_file = tmp_path / "frozen_key.p8"
    key_file.write_text("content")

    monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "test-account")
    monkeypatch.setenv("SNOWFLAKE_USER", "test-user")
    monkeypatch.setenv("SNOWFLAKE_PRIVATE_KEY_PATH", str(key_file))

    settings = SnowflakeSettings()

    with pytest.raises(ValidationError):
        settings.snowflake_account = "new-account"  # type: ignore[misc]
