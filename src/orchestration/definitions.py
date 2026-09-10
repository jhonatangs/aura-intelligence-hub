"""Dagster definitions entrypoint for Aura Intelligence Hub.

Consolidates Software-Defined Assets (Bronze, Silver, Gold), automated Data Quality
Asset Checks, scheduled execution Jobs, cron Automations, and configured resources.
"""

from dagster import (
    Definitions,
    load_asset_checks_from_modules,
    load_assets_from_modules,
)

from src.orchestration.assets import bronze, gold, silver
from src.orchestration.checks import quality_checks
from src.orchestration.jobs import all_jobs, all_schedules
from src.orchestration.resources import SnowflakeResource

# Load all assets across Medallion layers
all_assets = load_assets_from_modules([bronze, silver, gold])

# Load data quality assertions
all_checks = load_asset_checks_from_modules([quality_checks])

# Consolidated Dagster repository definitions
defs = Definitions(
    assets=all_assets,
    asset_checks=all_checks,
    jobs=all_jobs,
    schedules=all_schedules,
    resources={
        "snowflake": SnowflakeResource(),
    },
)
