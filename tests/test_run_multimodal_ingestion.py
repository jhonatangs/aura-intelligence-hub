"""Unit tests for multimodal ingestion pipeline CLI entrypoint."""

from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.ingestion.models.multimodal import CompetitorPriceRecord, WeatherMetricRecord
from src.ingestion.pipelines.run_multimodal_ingestion import (
    parse_args,
    run_competitor_ingestion,
    run_inventory_ingestion,
    run_multimodal_pipeline,
    run_weather_ingestion,
)


def test_parse_args_defaults() -> None:
    """Verify default CLI argument parsing."""
    args = parse_args([])
    assert args.source == "all"
    assert args.dry_run is False
    assert args.inventory_dir == "data/raw/partners"


def test_parse_args_explicit() -> None:
    """Verify explicit CLI argument parsing."""
    args = parse_args(["--source", "weather", "--dry-run", "--start-date", "2026-03-01"])
    assert args.source == "weather"
    assert args.dry_run is True
    assert args.start_date == "2026-03-01"


def test_run_weather_ingestion_dry_run() -> None:
    """Verify weather ingestion execution in dry-run mode."""
    mock_records = [
        WeatherMetricRecord(
            city_hub="São Paulo",
            state="SP",
            date=date(2026, 3, 10),
            temp_max=30.0,
            temp_min=20.0,
            precipitation_sum=0.0,
        )
    ]
    patch_open_meteo = "src.ingestion.pipelines.run_multimodal_ingestion.OpenMeteoClient"
    with patch(patch_open_meteo) as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.fetch_all_hubs_weather.return_value = mock_records

        count = run_weather_ingestion(dry_run=True)
        assert count == 1
        instance.fetch_all_hubs_weather.assert_called_once()


@pytest.mark.anyio
async def test_run_competitor_ingestion_dry_run() -> None:
    """Verify competitor scraper execution in dry-run mode with mock records."""
    mock_records = [
        CompetitorPriceRecord(
            competitor_brand="RED_BULL",
            product_title="Red Bull 250ml",
            volume_ml=250,
            price_brl=9.99,
        )
    ]
    count = await run_competitor_ingestion(dry_run=True, mock_records=mock_records)
    assert count == 1


def test_run_inventory_ingestion_dry_run(tmp_path: Path) -> None:
    """Verify inventory file ingestion in dry-run mode."""
    test_csv = tmp_path / "inventory.csv"
    test_csv.write_text(
        "partner_id,sku,batch_id,stock_quantity,warehouse_location,snapshot_date\n"
        "P1,AURA_250ML,B1,100,WH1,2026-03-01\n",
        encoding="utf-8",
    )
    count = run_inventory_ingestion(inventory_dir=tmp_path, dry_run=True)
    assert count == 1


def test_run_multimodal_pipeline_orchestrator(tmp_path: Path) -> None:
    """Verify pipeline orchestrator dispatches selected sources."""
    base = "src.ingestion.pipelines.run_multimodal_ingestion"
    with (
        patch(f"{base}.run_weather_ingestion") as mock_w,
        patch(f"{base}.run_competitor_ingestion", new_callable=AsyncMock) as mock_c,
        patch(f"{base}.run_inventory_ingestion") as mock_i,
    ):
        status = run_multimodal_pipeline(source="all", dry_run=True, inventory_dir=str(tmp_path))
        assert status == 0
        mock_w.assert_called_once()
        mock_c.assert_called_once()
        mock_i.assert_called_once()
