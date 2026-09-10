"""Integration tests for End-to-End Lakehouse Pipeline Runner and Telemetry.

Validates end-to-end lifecycle orchestration, stage sequencing, argument parsing,
failure boundaries, and telemetry capture across mocked Bronze, Silver, Gold, and
Data Quality checking phases.
"""

from unittest.mock import MagicMock, patch

from scripts.run_e2e_pipeline import E2EPipelineRunner, main, parse_args

MOCK_SILVER_RESULTS = {
    "invoices": {"status": "success", "rows_affected": 15},
    "invoice_items": {"status": "success", "rows_affected": 30},
    "competitor_prices": {"status": "success", "rows_affected": 20},
    "weather_metrics": {"status": "success", "rows_affected": 10},
    "partner_inventory": {"status": "success", "rows_affected": 25},
}

MOCK_GOLD_RESULTS = {
    "dimensions": {
        "gold_dim_date": {"status": "success", "rows_affected": 1826},
        "gold_dim_partners": {"status": "success", "rows_affected": 5},
        "gold_dim_skus": {"status": "success", "rows_affected": 3},
        "gold_dim_hubs": {"status": "success", "rows_affected": 10},
    },
    "facts": {
        "gold_fact_sellout": {"status": "success", "rows_affected": 30},
        "gold_fact_inventory_snapshot": {"status": "success", "rows_affected": 25},
        "gold_fact_competitor_pricing": {"status": "success", "rows_affected": 20},
    },
}


# -----------------------------------------------------------------------------
# Argument Parsing Tests
# -----------------------------------------------------------------------------


def test_parse_args_defaults() -> None:
    """Verify default CLI arguments."""
    args = parse_args([])
    assert args.dry_run is False
    assert args.database is None
    assert args.skip_ingestion is False
    assert args.skip_checks is False


def test_parse_args_explicit_flags() -> None:
    """Verify explicit CLI arguments."""
    args = parse_args(
        [
            "--dry-run",
            "--database",
            "CUSTOM_DB",
            "--skip-ingestion",
            "--skip-checks",
        ]
    )
    assert args.dry_run is True
    assert args.database == "CUSTOM_DB"
    assert args.skip_ingestion is True
    assert args.skip_checks is True


# -----------------------------------------------------------------------------
# End-to-End Orchestrator Tests
# -----------------------------------------------------------------------------


def test_e2e_pipeline_dry_run_execution() -> None:
    """Verify end-to-end execution in dry-run mode completes with code 0."""
    runner = E2EPipelineRunner(dry_run=True, skip_ingestion=True)
    exit_code = runner.execute()

    assert exit_code == 0
    assert len(runner.telemetry) == 4
    assert runner.telemetry[0].status == "SKIPPED"
    assert runner.telemetry[1].status == "SUCCESS"
    assert runner.telemetry[2].status == "SUCCESS"
    assert runner.telemetry[3].status == "SUCCESS"


def test_e2e_pipeline_full_success_mocked() -> None:
    """Verify full end-to-end pipeline execution across all 4 stages."""
    mock_silver_svc = MagicMock()
    mock_silver_svc.transform_all.return_value = MOCK_SILVER_RESULTS

    mock_gold_svc = MagicMock()
    mock_gold_svc.transform_all.return_value = MOCK_GOLD_RESULTS

    mock_client = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (0,)
    mock_client.get_cursor.return_value.__enter__.return_value = mock_cursor

    runner = E2EPipelineRunner(database="TEST_DB", dry_run=False)

    with (
        patch(
            "src.ingestion.pipelines.run_invoice_ingestion.run_pipeline",
            return_value=0,
        ),
        patch(
            "src.ingestion.pipelines.run_multimodal_ingestion.run_multimodal_pipeline",
            return_value=0,
        ),
        patch("scripts.run_e2e_pipeline.SilverTransformationService", return_value=mock_silver_svc),
        patch("scripts.run_e2e_pipeline.GoldTransformationService", return_value=mock_gold_svc),
        patch("scripts.run_e2e_pipeline.SnowflakeClient", return_value=mock_client),
    ):
        exit_code = runner.execute()

    assert exit_code == 0
    assert len(runner.telemetry) == 4

    # Bronze
    assert runner.telemetry[0].stage_name == "Bronze Ingestion"
    assert runner.telemetry[0].status == "SUCCESS"

    # Silver
    assert runner.telemetry[1].stage_name == "Silver Cleansing"
    assert runner.telemetry[1].status == "SUCCESS"
    assert runner.telemetry[1].rows_affected == 100

    # Gold
    assert runner.telemetry[2].stage_name == "Gold Dimensional Modeling"
    assert runner.telemetry[2].status == "SUCCESS"
    assert runner.telemetry[2].rows_affected == (1826 + 5 + 3 + 10 + 30 + 25 + 20)

    # Checks
    assert runner.telemetry[3].stage_name == "Data Quality Checks"
    assert runner.telemetry[3].status == "SUCCESS"
    assert runner.telemetry[3].details["passed"] == 4
    assert runner.telemetry[3].details["failed"] == 0


def test_e2e_pipeline_bronze_failure_aborts() -> None:
    """Verify Bronze ingestion failure aborts subsequent stages."""
    runner = E2EPipelineRunner(dry_run=False)

    with patch(
        "src.ingestion.pipelines.run_invoice_ingestion.run_pipeline",
        side_effect=RuntimeError("PDF extraction crash"),
    ):
        exit_code = runner.execute()

    assert exit_code == 1
    assert len(runner.telemetry) == 1
    assert runner.telemetry[0].status == "FAILED"
    assert "PDF extraction crash" in str(runner.telemetry[0].error_message)


def test_e2e_pipeline_silver_failure_aborts() -> None:
    """Verify Silver stage failure aborts subsequent Gold and Check stages."""
    mock_silver_svc = MagicMock()
    mock_silver_svc.transform_all.side_effect = RuntimeError("Snowflake MERGE deadlock")

    runner = E2EPipelineRunner(skip_ingestion=True, dry_run=False)

    with patch(
        "scripts.run_e2e_pipeline.SilverTransformationService",
        return_value=mock_silver_svc,
    ):
        exit_code = runner.execute()

    assert exit_code == 1
    assert len(runner.telemetry) == 2
    assert runner.telemetry[0].status == "SKIPPED"
    assert runner.telemetry[1].status == "FAILED"
    assert "Snowflake MERGE deadlock" in str(runner.telemetry[1].error_message)


def test_e2e_pipeline_gold_failure_aborts() -> None:
    """Verify Gold stage failure aborts subsequent Check stage."""
    mock_silver_svc = MagicMock()
    mock_silver_svc.transform_all.return_value = MOCK_SILVER_RESULTS

    mock_gold_svc = MagicMock()
    mock_gold_svc.transform_all.side_effect = RuntimeError("Surrogate key generation error")

    runner = E2EPipelineRunner(skip_ingestion=True, dry_run=False)

    with (
        patch("scripts.run_e2e_pipeline.SilverTransformationService", return_value=mock_silver_svc),
        patch("scripts.run_e2e_pipeline.GoldTransformationService", return_value=mock_gold_svc),
    ):
        exit_code = runner.execute()

    assert exit_code == 1
    assert len(runner.telemetry) == 3
    assert runner.telemetry[2].status == "FAILED"
    assert "Surrogate key generation error" in str(runner.telemetry[2].error_message)


def test_e2e_pipeline_quality_checks_failure() -> None:
    """Verify failed data quality assertions mark pipeline as failure with exit code 1."""
    mock_silver_svc = MagicMock()
    mock_silver_svc.transform_all.return_value = MOCK_SILVER_RESULTS

    mock_gold_svc = MagicMock()
    mock_gold_svc.transform_all.return_value = MOCK_GOLD_RESULTS

    mock_client = MagicMock()
    mock_cursor = MagicMock()
    # Simulate non-null violations = 3
    mock_cursor.fetchone.return_value = (3,)
    mock_client.get_cursor.return_value.__enter__.return_value = mock_cursor

    runner = E2EPipelineRunner(skip_ingestion=True, dry_run=False)

    with (
        patch("scripts.run_e2e_pipeline.SilverTransformationService", return_value=mock_silver_svc),
        patch("scripts.run_e2e_pipeline.GoldTransformationService", return_value=mock_gold_svc),
        patch("scripts.run_e2e_pipeline.SnowflakeClient", return_value=mock_client),
    ):
        exit_code = runner.execute()

    assert exit_code == 1
    assert len(runner.telemetry) == 4
    assert runner.telemetry[3].status == "FAILED"
    assert runner.telemetry[3].details["failed"] > 0


def test_main_cli_entrypoint(monkeypatch) -> None:
    """Verify main() entrypoint triggers E2EPipelineRunner."""
    monkeypatch.setattr(
        "sys.argv",
        ["run_e2e_pipeline.py", "--dry-run", "--skip-ingestion", "--skip-checks"],
    )

    with patch.object(E2EPipelineRunner, "execute", return_value=0) as mock_exec:
        try:
            main()
        except SystemExit as exc:
            assert exc.code == 0
        mock_exec.assert_called_once()
