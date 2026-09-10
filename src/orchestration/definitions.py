"""Dagster definitions entrypoint for Aura Intelligence Hub.

Registers software-defined assets, schedules, and resources for the lakehouse platform.
"""

from dagster import Definitions, load_assets_from_modules

from src.orchestration.assets import bronze

all_assets = load_assets_from_modules([bronze])

defs = Definitions(
    assets=all_assets,
)
