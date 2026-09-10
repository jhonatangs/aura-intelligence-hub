"""Unit tests for Bronze multimodal repositories with mocked SnowflakeClient."""

from datetime import date
from unittest.mock import MagicMock

import pytest

from src.common.snowflake_client import SnowflakeClient
from src.ingestion.models.multimodal import (
    CompetitorPriceRecord,
    PartnerInventoryRecord,
    WeatherMetricRecord,
)
from src.ingestion.repositories.bronze_competitor_repo import (
    BronzeCompetitorPriceRepository,
    get_competitor_insert_sql,
)
from src.ingestion.repositories.bronze_inventory_repo import (
    BronzePartnerInventoryRepository,
    get_inventory_insert_sql,
)
from src.ingestion.repositories.bronze_weather_repo import (
    BronzeWeatherRepository,
    get_weather_insert_sql,
)


@pytest.fixture
def mock_client() -> MagicMock:
    """Fixture providing a mock SnowflakeClient with managed cursor context."""
    client = MagicMock(spec=SnowflakeClient)
    client.is_connected = True
    cursor_mock = MagicMock()
    client.managed_cursor.return_value.__enter__.return_value = cursor_mock
    client.managed_cursor.return_value.__exit__.return_value = None
    return client


class TestBronzeCompetitorPriceRepository:
    """Test suite for BronzeCompetitorPriceRepository."""

    def test_sql_paramstyles(self) -> None:
        """Verify SQL generation adapts to qmark or pyformat."""
        sql_q = get_competitor_insert_sql("qmark")
        assert "PARSE_JSON(?)" in sql_q
        assert "SELECT ?, ?, CURRENT_TIMESTAMP(), PARSE_JSON(?)" in sql_q

        sql_p = get_competitor_insert_sql("pyformat")
        assert "PARSE_JSON(%s)" in sql_p
        assert "SELECT %s, %s, CURRENT_TIMESTAMP(), PARSE_JSON(%s)" in sql_p

    def test_insert_price_record(self, mock_client: MagicMock) -> None:
        """Verify single record insertion using CompetitorPriceRecord."""
        repo = BronzeCompetitorPriceRepository(client=mock_client)
        rec = CompetitorPriceRecord(
            competitor_brand="RED_BULL",
            product_title="Red Bull 250ml",
            volume_ml=250,
            price_brl=9.99,
            stock_status="IN_STOCK",
            source_url="https://mock.com/redbull",
        )
        repo.insert_price_record("https://mock.com/redbull", "RED_BULL", rec, paramstyle="qmark")

        cursor = mock_client.managed_cursor.return_value.__enter__.return_value
        cursor.execute.assert_called_once()
        args, _ = cursor.execute.call_args
        assert "AURA_LAKEHOUSE.BRONZE.COMPETITOR_PRICES_RAW" in args[0]
        assert args[1][0] == "https://mock.com/redbull"
        assert args[1][1] == "RED_BULL"
        assert "Red Bull 250ml" in args[1][2]

    def test_batch_insert_records(self, mock_client: MagicMock) -> None:
        """Verify batch insertion of multiple competitor prices."""
        repo = BronzeCompetitorPriceRepository(client=mock_client)
        rec1 = CompetitorPriceRecord(
            competitor_brand="RED_BULL",
            product_title="Red Bull 250ml",
            volume_ml=250,
            price_brl=9.99,
        )
        rec2 = CompetitorPriceRecord(
            competitor_brand="MONSTER",
            product_title="Monster 473ml",
            volume_ml=473,
            price_brl=11.50,
        )
        count = repo.batch_insert_price_records(
            [
                ("https://mock.com/1", "RED_BULL", rec1),
                ("https://mock.com/2", "MONSTER", rec2),
            ]
        )
        assert count == 2
        cursor = mock_client.managed_cursor.return_value.__enter__.return_value
        assert cursor.execute.call_count == 2

    def test_invalid_payload_raises(self, mock_client: MagicMock) -> None:
        """Verify TypeError when invalid payload type is passed."""
        repo = BronzeCompetitorPriceRepository(client=mock_client)
        with pytest.raises(TypeError):
            repo.insert_price_record("http", "RED_BULL", "invalid_string_payload")  # type: ignore


class TestBronzeWeatherRepository:
    """Test suite for BronzeWeatherRepository."""

    def test_sql_paramstyles(self) -> None:
        """Verify SQL generation adapts to placeholders."""
        sql_q = get_weather_insert_sql("qmark")
        assert "PARSE_JSON(?)" in sql_q
        assert "SELECT ?, ?, CURRENT_TIMESTAMP(), PARSE_JSON(?)" in sql_q

    def test_insert_weather_record(self, mock_client: MagicMock) -> None:
        """Verify single record insertion for weather metrics."""
        repo = BronzeWeatherRepository(client=mock_client)
        rec = WeatherMetricRecord(
            city_hub="São Paulo",
            state="SP",
            date=date(2026, 3, 10),
            temp_max=32.0,
            temp_min=21.0,
            precipitation_sum=0.0,
        )
        repo.insert_weather_record("São Paulo", "SP", rec, paramstyle="qmark")

        cursor = mock_client.managed_cursor.return_value.__enter__.return_value
        cursor.execute.assert_called_once()
        args, _ = cursor.execute.call_args
        assert "AURA_LAKEHOUSE.BRONZE.WEATHER_METRICS_RAW" in args[0]
        assert args[1][0] == "São Paulo"
        assert args[1][1] == "SP"

    def test_batch_insert_weather(self, mock_client: MagicMock) -> None:
        """Verify batch insertion of weather records."""
        repo = BronzeWeatherRepository(client=mock_client)
        rec = WeatherMetricRecord(
            city_hub="Curitiba",
            state="PR",
            date=date(2026, 3, 10),
            temp_max=24.0,
            temp_min=15.0,
            precipitation_sum=5.2,
        )
        count = repo.batch_insert_weather_records([("Curitiba", "PR", rec)])
        assert count == 1


class TestBronzePartnerInventoryRepository:
    """Test suite for BronzePartnerInventoryRepository."""

    def test_sql_paramstyles(self) -> None:
        """Verify SQL generation adapts to placeholders."""
        sql_q = get_inventory_insert_sql("qmark")
        assert "PARSE_JSON(?)" in sql_q
        assert "CURRENT_TIMESTAMP(), PARSE_JSON(?)" in sql_q

        sql_p = get_inventory_insert_sql("pyformat")
        assert "PARSE_JSON(%s)" in sql_p
        assert "CURRENT_TIMESTAMP(), PARSE_JSON(%s)" in sql_p

    def test_insert_inventory_record(self, mock_client: MagicMock) -> None:
        """Verify single inventory record insertion."""
        repo = BronzePartnerInventoryRepository(client=mock_client)
        rec = PartnerInventoryRecord(
            partner_id="PARTNER_SP",
            sku="AURA_250ML",
            batch_id="BATCH-01",
            stock_quantity=1200,
            warehouse_location="WH-1",
            snapshot_date=date(2026, 3, 1),
        )
        repo.insert_inventory_record(
            "inventory_sp.csv",
            "PARTNER_SP",
            "d41d8cd98f00b204e9800998ecf8427e",
            rec,
            paramstyle="qmark",
        )

        cursor = mock_client.managed_cursor.return_value.__enter__.return_value
        cursor.execute.assert_called_once()
        args, _ = cursor.execute.call_args
        assert "AURA_LAKEHOUSE.BRONZE.PARTNER_INVENTORY_RAW" in args[0]
        assert args[1][0] == "inventory_sp.csv"
        assert args[1][1] == "PARTNER_SP"
        assert args[1][2] == "d41d8cd98f00b204e9800998ecf8427e"

    def test_batch_insert_inventory(self, mock_client: MagicMock) -> None:
        """Verify batch insertion of inventory records."""
        repo = BronzePartnerInventoryRepository(client=mock_client)
        rec = PartnerInventoryRecord(
            partner_id="PARTNER_RJ",
            sku="AURA_ZERO_250ML",
            batch_id="BATCH-02",
            stock_quantity=600,
            warehouse_location="WH-2",
            snapshot_date=date(2026, 3, 1),
        )
        count = repo.batch_insert_inventory_records(
            [("inventory_rj.csv", "PARTNER_RJ", "md5hash", rec)]
        )
        assert count == 1
