"""Pipeline CLI entrypoint for Gold layer dimensional transformations.

Executes push-down SQL transformations to materialize Kimball star-schema
dimensions and facts from Silver conformed tables into the Gold layer.

Supports `--target` (`dimensions`, `facts`, `all`) and `--dry-run` switches.
"""

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

# Ensure project root is on sys.path for direct CLI execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.transformation.services.gold_service import GoldTransformationService  # noqa: E402
from src.transformation.sql.gold_transforms import (  # noqa: E402
    get_all_gold_dimension_queries,
    get_all_gold_fact_queries,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("aura.transformation.gold")


def run_gold_pipeline(
    target: str = "all",
    dry_run: bool = False,
    database: str | None = None,
    service: GoldTransformationService | None = None,
) -> int:
    """Execute the Gold transformation pipeline.

    Args:
        target: Target models ('all', 'dimensions', 'facts').
        dry_run: If True, preview generated SQL statements without executing on Snowflake.
        database: Optional Snowflake database name override.
        service: Optional GoldTransformationService instance for dependency injection.

    Returns:
        int: Exit status code (0 for success, 1 for failure).
    """
    target_clean = target.lower().strip()
    db = database or "AURA_LAKEHOUSE"

    logger.info(
        "Initiating Gold transformation pipeline [target=%s, dry_run=%s, database=%s]",
        target_clean,
        dry_run,
        db,
    )

    if dry_run:
        logger.info("[DRY-RUN] Generating Gold transformation SQL without executing...")
        queries: dict[str, str] = {}

        if target_clean in ("all", "dimensions"):
            queries.update(get_all_gold_dimension_queries(db))
        if target_clean in ("all", "facts"):
            queries.update(get_all_gold_fact_queries(db))

        for model_name, stmt in queries.items():
            logger.info("[DRY-RUN] [%s]:\n%s", model_name, stmt)

        logger.info("[DRY-RUN] Completed SQL generation for target '%s'.", target_clean)
        return 0

    svc = service or GoldTransformationService(database=database)

    try:
        with svc:
            if target_clean == "all":
                summary = svc.transform_all()
                logger.info("Successfully executed all Gold transforms: %s", summary)
            elif target_clean == "dimensions":
                res = svc.transform_dimensions()
                logger.info("Successfully transformed Gold dimensions: %s", res)
            elif target_clean == "facts":
                res = svc.transform_facts()
                logger.info("Successfully transformed Gold facts: %s", res)
            else:
                logger.error("Unknown transformation target: '%s'", target)
                return 1

        logger.info("Gold transformation pipeline completed successfully.")
        return 0
    except Exception as err:
        logger.error("Gold transformation pipeline failed: %s", err, exc_info=True)
        return 1


def parse_args(args: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Aura Intelligence Hub - Gold Layer Transformation Pipeline CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--target",
        choices=["all", "dimensions", "facts"],
        default="all",
        help="Target models to transform (dimensions, facts, or all).",
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
    status = run_gold_pipeline(
        target=parsed.target,
        dry_run=parsed.dry_run,
        database=parsed.database,
    )
    sys.exit(status)


if __name__ == "__main__":
    main()
