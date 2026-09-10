"""Unit tests for Silver transformation pipeline CLI runner."""

from unittest.mock import MagicMock

import pytest

from src.transformation.pipelines.run_silver_transforms import (
    parse_args,
    run_silver_pipeline,
)


def test_parse_args_defaults() -> None:
    """Verify default CLI arguments."""
    args = parse_args([])
    assert args.target == "all"
    assert not args.dry_run
    assert args.database is None


def test_parse_args_custom() -> None:
    """Verify custom CLI argument parsing."""
    args = parse_args(["--target", "invoices", "--dry-run", "--database", "TEST_DB"])
    assert args.target == "invoices"
    assert args.dry_run is True
    assert args.database == "TEST_DB"


def test_parse_args_invalid_target() -> None:
    """Verify error on invalid target choice."""
    with pytest.raises(SystemExit):
        parse_args(["--target", "invalid_choice"])


def test_run_silver_pipeline_dry_run() -> None:
    """Verify dry-run mode succeeds without invoking database services."""
    mock_service = MagicMock()
    status = run_silver_pipeline(target="all", dry_run=True, service=mock_service)
    assert status == 0
    mock_service.transform_all.assert_not_called()


def test_run_silver_pipeline_all_target() -> None:
    """Verify pipeline executes transform_all for 'all' target."""
    mock_service = MagicMock()
    mock_service.__enter__.return_value = mock_service
    mock_service.transform_all.return_value = {"status": "success", "total_rows_affected": 10}

    status = run_silver_pipeline(target="all", dry_run=False, service=mock_service)
    assert status == 0
    mock_service.transform_all.assert_called_once()


def test_run_silver_pipeline_individual_targets() -> None:
    """Verify pipeline routes to proper service methods for individual targets."""
    mock_service = MagicMock()
    mock_service.__enter__.return_value = mock_service

    for target, method_name in [
        ("invoices", "transform_invoices"),
        ("competitors", "transform_competitor_prices"),
        ("weather", "transform_weather_metrics"),
        ("inventory", "transform_partner_inventory"),
    ]:
        status = run_silver_pipeline(target=target, dry_run=False, service=mock_service)
        assert status == 0
        getattr(mock_service, method_name).assert_called_once()
        getattr(mock_service, method_name).reset_mock()


def test_run_silver_pipeline_failure() -> None:
    """Verify pipeline returns exit code 1 on service exception."""
    mock_service = MagicMock()
    mock_service.__enter__.return_value = mock_service
    mock_service.transform_all.side_effect = RuntimeError("Snowflake connection lost")

    status = run_silver_pipeline(target="all", dry_run=False, service=mock_service)
    assert status == 1
