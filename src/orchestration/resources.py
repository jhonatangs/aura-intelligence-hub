"""Dagster resource definitions for Aura Intelligence Hub.

Provides managed, typed resource connectors for Snowflake and peripheral platform services.
"""

from dagster import ConfigurableResource
from pydantic import Field

from src.common.snowflake_client import SnowflakeClient


class SnowflakeResource(ConfigurableResource):
    """Dagster resource providing managed access to Snowflake Lakehouse client.

    Wraps RSA key-pair authentication and connection pooling lifecycle.
    """

    warehouse: str = Field(default="COMPUTE_WH", description="Target virtual warehouse")
    database: str = Field(default="AURA_LAKEHOUSE", description="Target Lakehouse database")
    schema_name: str = Field(default="BRONZE", description="Default working schema")
    role: str = Field(default="ACCOUNTADMIN", description="Active Snowflake role")

    def get_client(self) -> SnowflakeClient:
        """Instantiate and return a configured SnowflakeClient.

        Returns:
            SnowflakeClient: Managed Snowflake connection client.
        """
        return SnowflakeClient()
