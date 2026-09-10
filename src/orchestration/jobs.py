"""Dagster job and schedule definitions for Aura Intelligence Hub.

Declares materialization jobs and cron automation schedules for end-to-end
lakehouse processing and targeted intraday market intelligence updates.
"""

from dagster import (
    AssetSelection,
    ScheduleDefinition,
    define_asset_job,
)

# -----------------------------------------------------------------------------
# Asset Selection Specifications
# -----------------------------------------------------------------------------

LAKEHOUSE_E2E_SELECTION = AssetSelection.groups("bronze", "silver", "gold")

INTRADAY_MARKET_INTELLIGENCE_SELECTION = AssetSelection.assets(
    "bronze_competitor_prices_raw",
    "bronze_weather_metrics_raw",
    "silver_competitor_prices",
    "silver_weather_metrics",
    "gold_fact_competitor_pricing",
)

# -----------------------------------------------------------------------------
# Jobs
# -----------------------------------------------------------------------------

lakehouse_e2e_job = define_asset_job(
    name="lakehouse_e2e_job",
    selection=LAKEHOUSE_E2E_SELECTION,
    description=(
        "End-to-end materialization job orchestrating the complete Medallion Lakehouse "
        "(Bronze Ingestion -> Silver Cleansing & Conformation -> Gold Dimensional Modeling)."
    ),
)

intraday_market_intelligence_job = define_asset_job(
    name="intraday_market_intelligence_job",
    selection=INTRADAY_MARKET_INTELLIGENCE_SELECTION,
    description=(
        "Targeted intraday execution updating competitor retail prices, regional weather metrics, "
        "and competitive market benchmarking marts."
    ),
)

all_jobs = [
    lakehouse_e2e_job,
    intraday_market_intelligence_job,
]

# -----------------------------------------------------------------------------
# Automation Schedules (Timezone: America/Sao_Paulo)
# -----------------------------------------------------------------------------

daily_lakehouse_schedule = ScheduleDefinition(
    job=lakehouse_e2e_job,
    cron_schedule="0 3 * * *",
    execution_timezone="America/Sao_Paulo",
    name="daily_lakehouse_schedule",
    description="Daily full Medallion lakehouse materialization at 03:00 AM America/Sao_Paulo.",
)

intraday_market_intelligence_schedule = ScheduleDefinition(
    job=intraday_market_intelligence_job,
    cron_schedule="0 */4 * * *",
    execution_timezone="America/Sao_Paulo",
    name="intraday_market_intelligence_schedule",
    description=(
        "Intraday market intelligence refresh every 4 hours in America/Sao_Paulo "
        "for competitor price monitoring and weather correlation."
    ),
)

all_schedules = [
    daily_lakehouse_schedule,
    intraday_market_intelligence_schedule,
]
