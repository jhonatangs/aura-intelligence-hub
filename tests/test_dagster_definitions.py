"""Unit tests for consolidated Dagster Definitions repository.

Validates asset key resolution across Medallion layers, data quality check registrations,
job asset selection sets, cron schedule configurations, resource bindings, and absence
of circular dependencies.
"""

from unittest.mock import MagicMock, patch

from src.orchestration.definitions import defs
from src.orchestration.jobs import (
    all_jobs,
    all_schedules,
    daily_lakehouse_schedule,
    intraday_market_intelligence_job,
    intraday_market_intelligence_schedule,
    lakehouse_e2e_job,
)
from src.orchestration.resources import SnowflakeResource


def test_asset_registry_contains_all_layers() -> None:
    """Verify all 16 Medallion assets are registered in Definitions."""
    resolved_keys = {key.path[-1] for key in defs.resolve_all_asset_keys()}

    expected_bronze = {
        "bronze_invoices_raw",
        "bronze_weather_metrics_raw",
        "bronze_competitor_prices_raw",
        "bronze_partner_inventory_raw",
    }
    expected_silver = {
        "silver_invoices",
        "silver_invoice_items",
        "silver_competitor_prices",
        "silver_weather_metrics",
        "silver_partner_inventory",
    }
    expected_gold = {
        "gold_dim_date",
        "gold_dim_partners",
        "gold_dim_skus",
        "gold_dim_hubs",
        "gold_fact_sellout",
        "gold_fact_inventory_snapshot",
        "gold_fact_competitor_pricing",
    }

    all_expected = expected_bronze | expected_silver | expected_gold
    assert all_expected.issubset(resolved_keys)
    assert len(all_expected) == 16


def test_asset_checks_registration() -> None:
    """Verify all 4 data quality asset checks are registered in Definitions."""
    registered_check_names = {
        check_key.name
        for check_def in (defs.asset_checks or [])
        for check_key in check_def.check_keys
    }

    expected_checks = {
        "check_sellout_surrogate_keys_not_null",
        "check_sellout_positive_revenue",
        "check_inventory_non_negative_balances",
        "check_competitor_price_bounds",
    }
    assert expected_checks == registered_check_names


def test_lakehouse_e2e_job_selection() -> None:
    """Verify lakehouse_e2e_job selects all 16 assets across bronze, silver, and gold."""
    job_def = defs.get_job_def("lakehouse_e2e_job")
    selected_keys = {key.path[-1] for key in job_def.asset_layer.selected_asset_keys}

    assert len(selected_keys) == 16
    assert "bronze_invoices_raw" in selected_keys
    assert "silver_invoices" in selected_keys
    assert "gold_fact_sellout" in selected_keys


def test_intraday_market_intelligence_job_selection() -> None:
    """Verify intraday_market_intelligence_job targets only competitor and weather assets."""
    job_def = defs.get_job_def("intraday_market_intelligence_job")
    selected_keys = {key.path[-1] for key in job_def.asset_layer.selected_asset_keys}

    expected_intraday = {
        "bronze_competitor_prices_raw",
        "bronze_weather_metrics_raw",
        "silver_competitor_prices",
        "silver_weather_metrics",
        "gold_fact_competitor_pricing",
    }
    assert selected_keys == expected_intraday


def test_schedule_definitions() -> None:
    """Verify schedule cron strings, target jobs, and execution timezones."""
    schedules_by_name = {s.name: s for s in defs.schedules or []}

    # Daily E2E Schedule
    assert "daily_lakehouse_schedule" in schedules_by_name
    daily_s = schedules_by_name["daily_lakehouse_schedule"]
    assert daily_s.cron_schedule == "0 3 * * *"
    assert daily_s.execution_timezone == "America/Sao_Paulo"
    assert daily_s.job_name == "lakehouse_e2e_job"

    # Intraday Schedule
    assert "intraday_market_intelligence_schedule" in schedules_by_name
    intraday_s = schedules_by_name["intraday_market_intelligence_schedule"]
    assert intraday_s.cron_schedule == "0 */4 * * *"
    assert intraday_s.execution_timezone == "America/Sao_Paulo"
    assert intraday_s.job_name == "intraday_market_intelligence_job"


def test_no_circular_dependencies_in_dag() -> None:
    """Assert absence of circular dependencies in the full asset dependency graph."""
    job_def = defs.get_job_def("lakehouse_e2e_job")
    toposorted = [key.path[-1] for key in job_def.asset_layer.asset_graph.toposorted_asset_keys]

    assert len(toposorted) == 16

    # Verify topological ordering: bronze comes before silver, silver before gold
    assert toposorted.index("bronze_invoices_raw") < toposorted.index("silver_invoices")
    assert toposorted.index("silver_invoices") < toposorted.index("gold_fact_sellout")
    assert toposorted.index("gold_dim_date") < toposorted.index("gold_fact_sellout")


def test_snowflake_resource_configuration() -> None:
    """Verify configured Snowflake resource in Definitions."""
    assert "snowflake" in defs.resources
    resource = defs.resources["snowflake"]
    assert isinstance(resource, SnowflakeResource)
    assert resource.database == "AURA_LAKEHOUSE"
    assert resource.warehouse == "COMPUTE_WH"

    mock_client = MagicMock()
    with patch("src.orchestration.resources.SnowflakeClient", return_value=mock_client):
        client = resource.get_client()
        assert client is mock_client


def test_jobs_and_schedules_module_exports() -> None:
    """Verify jobs and schedules exported from src.orchestration.jobs."""
    assert len(all_jobs) == 2
    assert lakehouse_e2e_job in all_jobs
    assert intraday_market_intelligence_job in all_jobs

    assert len(all_schedules) == 2
    assert daily_lakehouse_schedule in all_schedules
    assert intraday_market_intelligence_schedule in all_schedules
