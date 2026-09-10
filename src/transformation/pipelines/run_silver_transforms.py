"""Pipeline CLI entrypoint for Silver layer transformations.

Executes push-down SQL transformations to promote Bronze raw variant payloads
into conformed, deduplicated Silver relational models.

Supports `--target` (`all`, `invoices`, `competitors`, `weather`, `inventory`)
and `--dry-run` switches for isolated testing.
"""

import argparse
import logging
import sys
from collections.abc import Sequence

from src.transformation.services.silver_service import SilverTransformationService
from src.transformation.sql.silver_transforms import (
    build_merge_competitor_prices_sql,
    build_merge_invoice_items_sql,
    build_merge_invoices_sql,
    build_merge_partner_inventory_sql,
    build_merge_weather_metrics_sql,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("aura.transformation.silver")


def run_silver_pipeline(
    target: str = "all",
    dry_run: bool = False,
    database: str | None = None,
    service: SilverTransformationService | None = None,
) -> int:
    """Execute the Silver transformation pipeline.

    Args:
        target: Target dataset ('all', 'invoices', 'competitors', 'weather', 'inventory').
        dry_run: If True, prints generated SQL statements without running them on Snowflake.
        database: Optional Snowflake database name override.
        service: Optional SilverTransformationService instance for dependency injection.

    Returns:
        int: Exit status code (0 for success, 1 for failure).
    """
    target_clean = target.lower().strip()
    db = database or "AURA_LAKEHOUSE"

    logger.info(
        "Initiating Silver transformation pipeline [target=%s, dry_run=%s, database=%s]",
        target_clean,
        dry_run,
        db,
    )

    if dry_run:
        logger.info("[DRY-RUN] Generating transformation SQL statements without executing...")
        queries: dict[str, list[str]] = {}

        if target_clean in ("all", "invoices"):
            queries["invoices"] = [
                build_merge_invoices_sql(db),
                build_merge_invoice_items_sql(db),
            ]
        if target_clean in ("all", "competitors"):
            queries["competitors"] = [build_merge_competitor_prices_sql(db)]
        if target_clean in ("all", "weather"):
            queries["weather"] = [build_merge_weather_metrics_sql(db)]
        if target_clean in ("all", "inventory"):
            queries["inventory"] = [build_merge_partner_inventory_sql(db)]

        for group, stmts in queries.items():
            for idx, stmt in enumerate(stmts, 1):
                logger.info("[DRY-RUN] [%s statement %d]:\n%s", group, idx, stmt)

        logger.info("[DRY-RUN] Completed SQL generation for target '%s'.", target_clean)
        return 0

    svc = service or SilverTransformationService(database=database)

    try:
        with svc:
            if target_clean == "all":
                summary = svc.transform_all()
                logger.info("Successfully executed all Silver transforms: %s", summary)
            elif target_clean == "invoices":
                res = svc.transform_invoices()
                logger.info("Successfully transformed invoices: %s", res)
            elif target_clean == "competitors":
                res = svc.transform_competitor_prices()
                logger.info("Successfully transformed competitor prices: %s", res)
            elif target_clean == "weather":
                res = svc.transform_weather_metrics()
                logger.info("Successfully transformed weather metrics: %s", res)
            elif target_clean == "inventory":
                res = svc.transform_partner_inventory()
                logger.info("Successfully transformed partner inventory: %s", res)
            else:
                logger.error("Unknown transformation target: '%s'", target)
                return 1

        logger.info("Silver transformation pipeline completed successfully.")
        return 0
    except Exception as err:
        logger.error("Silver transformation pipeline failed: %s", err, exc_info=True)
        return 1


def parse_args(args: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Aura Intelligence Hub - Silver Layer Transformation Pipeline CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--target",
        choices=["all", "invoices", "competitors", "weather", "inventory"],
        default="all",
        help="Target dataset to transform.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Generate and preview SQL queries without executing on Snowflake.",
    )
    parser.add_argument(
        "--database",
        type=str,
        default=None,
        help="Snowflake target database name override.",
    )
    return parser.parse_args(args)


def main() -> None:
    """CLI script entrypoint."""
    parsed = parse_args()
    status = run_silver_pipeline(
        target=parsed.target,
        dry_run=parsed.dry_run,
        database=parsed.database,
    )
    sys.exit(status)


if __name__ == "__main__":
    main()
