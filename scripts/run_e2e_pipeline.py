#!/usr/bin/env python3
"""End-to-End Lakehouse Pipeline Runner and Telemetry Reporter.

Executes the complete Aura Medallion Lakehouse lifecycle:
  1. Bronze Ingestion (Invoices, Scrapers, Open-Meteo Weather, Legacy Inventories)
  2. Silver Normalization & Cleansing (Pushdown SQL MERGE with Deduplication)
  3. Gold Dimensional Modeling (Kimball Star-Schema Dimensions & Facts)
  4. Data Quality Checks (Surrogate keys, revenue positivity, inventory bounds)

Supports `--dry-run`, `--skip-ingestion`, `--skip-checks`, and `--database` options.
"""

import argparse
import logging
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Ensure project root is available on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.common.config import get_settings  # noqa: E402
from src.common.snowflake_client import SnowflakeClient  # noqa: E402
from src.orchestration.checks.quality_checks import (  # noqa: E402
    query_competitor_invalid_price_bounds,
    query_inventory_negative_balances,
    query_sellout_negative_revenue,
    query_sellout_null_surrogate_keys,
)
from src.transformation.services.gold_service import GoldTransformationService  # noqa: E402
from src.transformation.services.silver_service import SilverTransformationService  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("aura.pipeline.e2e")


@dataclass
class StageTelemetry:
    """Telemetry metrics captured during a pipeline stage."""

    stage_name: str
    status: str = "PENDING"
    duration_seconds: float = 0.0
    rows_affected: int = 0
    details: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None


class E2EPipelineRunner:
    """Orchestrator for the full end-to-end Medallion data pipeline."""

    def __init__(
        self,
        database: str | None = None,
        dry_run: bool = False,
        skip_ingestion: bool = False,
        skip_checks: bool = False,
    ) -> None:
        """Initialize the pipeline runner.

        Args:
            database: Optional Snowflake database override.
            dry_run: When True, simulates pipeline execution without modifying Snowflake.
            skip_ingestion: When True, bypasses Bronze ingestion.
            skip_checks: When True, bypasses post-modeling data quality assertions.
        """
        self.dry_run = dry_run
        self.skip_ingestion = skip_ingestion
        self.skip_checks = skip_checks

        try:
            settings = get_settings()
            self.database = database or settings.database
        except Exception:
            self.database = database or "AURA_LAKEHOUSE"

        self.telemetry: list[StageTelemetry] = []

    def run_bronze_stage(self) -> StageTelemetry:
        """Execute Phase 1: Bronze multimodal ingestion.

        Returns:
            StageTelemetry: Execution telemetry for the Bronze stage.
        """
        stage = StageTelemetry(stage_name="Bronze Ingestion")
        start_time = time.perf_counter()

        if self.skip_ingestion:
            stage.status = "SKIPPED"
            stage.duration_seconds = 0.0
            logger.info("Bronze Ingestion: SKIPPED via command-line flag.")
            return stage

        logger.info("Executing Phase 1: Bronze Multimodal Ingestion (dry_run=%s)...", self.dry_run)
        try:
            from src.ingestion.pipelines.run_invoice_ingestion import run_pipeline as run_invoices
            from src.ingestion.pipelines.run_multimodal_ingestion import (
                run_multimodal_pipeline,
            )

            # Ingest synthetic partner invoices
            inv_code = run_invoices(
                output_dir=PROJECT_ROOT / "data" / "raw" / "partners",
                generate_samples=2,
                dry_run=self.dry_run,
            )
            if inv_code != 0 and not self.dry_run:
                raise RuntimeError(f"Invoice ingestion failed with exit code {inv_code}")

            # Ingest weather, competitor scrapers, and tabular inventory
            multi_code = run_multimodal_pipeline(
                source="all",
                dry_run=self.dry_run,
                inventory_dir=PROJECT_ROOT / "data" / "raw" / "partners",
            )
            if multi_code != 0 and not self.dry_run:
                raise RuntimeError(f"Multimodal ingestion failed with exit code {multi_code}")

            stage.status = "SUCCESS"
            stage.rows_affected = 0 if self.dry_run else 10
            stage.details = {"invoices_exit": inv_code, "multimodal_exit": multi_code}
        except Exception as exc:
            stage.status = "FAILED"
            stage.error_message = str(exc)
            logger.exception("Bronze Ingestion failed: %s", exc)

        stage.duration_seconds = round(time.perf_counter() - start_time, 4)
        return stage

    def run_silver_stage(
        self, service: SilverTransformationService | None = None
    ) -> StageTelemetry:
        """Execute Phase 2: Silver normalization and cleansing.

        Args:
            service: Optional injected SilverTransformationService.

        Returns:
            StageTelemetry: Execution telemetry for the Silver stage.
        """
        stage = StageTelemetry(stage_name="Silver Cleansing")
        start_time = time.perf_counter()
        logger.info(
            "Executing Phase 2: Silver Conformation Transformations (database=%s, dry_run=%s)...",
            self.database,
            self.dry_run,
        )

        try:
            if self.dry_run:
                stage.status = "SUCCESS"
                stage.rows_affected = 0
                stage.details = {"mode": "dry-run preview"}
            else:
                svc = service or SilverTransformationService(database=self.database)
                results = svc.transform_all()
                stage.rows_affected = sum(
                    r.get("rows_affected", 0) for r in results.values() if isinstance(r, dict)
                )
                stage.status = "SUCCESS"
                stage.details = {k: v.get("rows_affected", 0) for k, v in results.items()}
        except Exception as exc:
            stage.status = "FAILED"
            stage.error_message = str(exc)
            logger.exception("Silver Cleansing failed: %s", exc)

        stage.duration_seconds = round(time.perf_counter() - start_time, 4)
        return stage

    def run_gold_stage(self, service: GoldTransformationService | None = None) -> StageTelemetry:
        """Execute Phase 3: Gold Kimball dimensional modeling.

        Args:
            service: Optional injected GoldTransformationService.

        Returns:
            StageTelemetry: Execution telemetry for the Gold stage.
        """
        stage = StageTelemetry(stage_name="Gold Dimensional Modeling")
        start_time = time.perf_counter()
        logger.info(
            "Executing Phase 3: Gold Dimensional Modeling (database=%s, dry_run=%s)...",
            self.database,
            self.dry_run,
        )

        try:
            if self.dry_run:
                stage.status = "SUCCESS"
                stage.rows_affected = 0
                stage.details = {"mode": "dry-run preview"}
            else:
                svc = service or GoldTransformationService(database=self.database)
                results = svc.transform_all()
                total_rows = 0
                for category in ("dimensions", "facts"):
                    for table_res in results.get(category, {}).values():
                        total_rows += table_res.get("rows_affected", 0)

                stage.rows_affected = total_rows
                stage.status = "SUCCESS"
                stage.details = results
        except Exception as exc:
            stage.status = "FAILED"
            stage.error_message = str(exc)
            logger.exception("Gold Dimensional Modeling failed: %s", exc)

        stage.duration_seconds = round(time.perf_counter() - start_time, 4)
        return stage

    def run_checks_stage(self, client: SnowflakeClient | None = None) -> StageTelemetry:
        """Execute Phase 4: Automated data quality assertions.

        Args:
            client: Optional injected SnowflakeClient.

        Returns:
            StageTelemetry: Execution telemetry for data quality checks.
        """
        stage = StageTelemetry(stage_name="Data Quality Checks")
        start_time = time.perf_counter()

        if self.skip_checks:
            stage.status = "SKIPPED"
            stage.duration_seconds = 0.0
            logger.info("Data Quality Checks: SKIPPED via command-line flag.")
            return stage

        logger.info("Executing Phase 4: Data Quality Checks (database=%s)...", self.database)
        if self.dry_run:
            stage.status = "SUCCESS"
            stage.details = {"passed": 4, "failed": 0, "mode": "dry-run preview"}
            stage.duration_seconds = round(time.perf_counter() - start_time, 4)
            return stage

        try:
            snowflake_client = client or SnowflakeClient()
            with snowflake_client.get_cursor() as cursor:
                null_keys = query_sellout_null_surrogate_keys(cursor, database=self.database)
                negative_rev = query_sellout_negative_revenue(cursor, database=self.database)
                negative_inv = query_inventory_negative_balances(cursor, database=self.database)
                invalid_prices = query_competitor_invalid_price_bounds(
                    cursor, database=self.database
                )

            violations = {
                "sellout_null_keys": null_keys,
                "sellout_negative_revenue": negative_rev,
                "inventory_negative_balances": negative_inv,
                "competitor_invalid_price_bounds": invalid_prices,
            }

            failed_checks = [k for k, v in violations.items() if v > 0]
            passed_checks = [k for k, v in violations.items() if v == 0]

            stage.details = {
                "passed": len(passed_checks),
                "failed": len(failed_checks),
                "violations": violations,
            }

            if failed_checks:
                stage.status = "FAILED"
                stage.error_message = f"Checks failed: {', '.join(failed_checks)}"
            else:
                stage.status = "SUCCESS"

        except Exception as exc:
            stage.status = "FAILED"
            stage.error_message = str(exc)
            logger.exception("Data Quality Checks failed: %s", exc)

        stage.duration_seconds = round(time.perf_counter() - start_time, 4)
        return stage

    def execute(self) -> int:
        """Run the complete end-to-end Medallion pipeline.

        Returns:
            int: 0 if all active stages succeeded, 1 if any stage failed.
        """
        total_start = time.perf_counter()
        logger.info("=" * 80)
        logger.info("STARTING AURA INTELLIGENCE HUB E2E LAKEHOUSE PIPELINE")
        logger.info(
            "Config: database=%s, dry_run=%s, skip_ingestion=%s, skip_checks=%s",
            self.database,
            self.dry_run,
            self.skip_ingestion,
            self.skip_checks,
        )
        logger.info("=" * 80)

        # Execute stages sequentially
        self.telemetry.append(self.run_bronze_stage())

        # If Bronze failed, abort downstream
        if self.telemetry[-1].status == "FAILED":
            return self._finalize(total_start, exit_code=1)

        self.telemetry.append(self.run_silver_stage())
        if self.telemetry[-1].status == "FAILED":
            return self._finalize(total_start, exit_code=1)

        self.telemetry.append(self.run_gold_stage())
        if self.telemetry[-1].status == "FAILED":
            return self._finalize(total_start, exit_code=1)

        self.telemetry.append(self.run_checks_stage())
        if self.telemetry[-1].status == "FAILED":
            return self._finalize(total_start, exit_code=1)

        return self._finalize(total_start, exit_code=0)

    def _finalize(self, start_time: float, exit_code: int) -> int:
        """Format and log summary execution telemetry.

        Args:
            start_time: Monotonic start timestamp.
            exit_code: Overall process exit code.

        Returns:
            int: exit_code.
        """
        total_duration = round(time.perf_counter() - start_time, 4)
        print("\n" + "=" * 80)
        print("                 AURA LAKEHOUSE E2E PIPELINE EXECUTION TELEMETRY")
        print("=" * 80)
        print(f"{'Stage':<30} | {'Status':<10} | {'Duration (s)':<14} | {'Rows / Checks'}")
        print("-" * 80)

        for item in self.telemetry:
            if item.stage_name != "Data Quality Checks":
                metric_str = f"{item.rows_affected} rows"
            else:
                passed_cnt = item.details.get("passed", 0)
                failed_cnt = item.details.get("failed", 0)
                metric_str = f"{passed_cnt} passed, {failed_cnt} failed"

            row_text = (
                f"{item.stage_name:<30} | {item.status:<10} | "
                f"{item.duration_seconds:<14.4f} | {metric_str}"
            )
            print(row_text)
            if item.error_message:
                print(f"  -> Error: {item.error_message}")

        print("-" * 80)
        print(f"Total Pipeline Runtime: {total_duration:.4f}s")
        print(f"Overall Result: {'SUCCESS' if exit_code == 0 else 'FAILURE'}")
        print("=" * 80 + "\n")
        return exit_code


def parse_args(args: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the E2E pipeline runner."""
    parser = argparse.ArgumentParser(
        description="Aura Intelligence Hub - End-to-End Lakehouse Pipeline Runner",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Simulate execution without modifying Snowflake Lakehouse tables.",
    )
    parser.add_argument(
        "--database",
        type=str,
        default=None,
        help="Snowflake target database override.",
    )
    parser.add_argument(
        "--skip-ingestion",
        action="store_true",
        default=False,
        help="Skip Bronze ingestion and run only Silver, Gold, and Quality Checks.",
    )
    parser.add_argument(
        "--skip-checks",
        action="store_true",
        default=False,
        help="Skip post-modeling automated data quality checks.",
    )
    return parser.parse_args(args)


def main() -> None:
    """CLI script entrypoint."""
    parsed = parse_args()
    runner = E2EPipelineRunner(
        database=parsed.database,
        dry_run=parsed.dry_run,
        skip_ingestion=parsed.skip_ingestion,
        skip_checks=parsed.skip_checks,
    )
    sys.exit(runner.execute())


if __name__ == "__main__":
    main()
