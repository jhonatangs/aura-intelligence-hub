"""Unit tests for BronzeInvoiceRepository mocking SnowflakeClient."""

import json
from datetime import date
from unittest.mock import MagicMock

import pytest

from src.common.snowflake_client import SnowflakeClient
from src.ingestion.models.invoice import (
    InvoiceItem,
    InvoiceMetadata,
    RawInvoicePayload,
)
from src.ingestion.repositories.bronze_invoice_repo import (
    BronzeInvoiceRepository,
    get_insert_sql,
)


@pytest.fixture
def sample_payload() -> RawInvoicePayload:
    """Fixture providing a valid invoice payload for repository testing."""
    return RawInvoicePayload(
        metadata=InvoiceMetadata(
            invoice_number="INV-BRONZE-01",
            partner_id="PARTNER_SP_01",
            partner_cnpj="00.000.000/0001-91",
            issue_date=date(2026, 9, 8),
        ),
        items=[
            InvoiceItem(
                sku="AURA_250ML",
                description="Aura Original Energy Drink 250ml",
                quantity=100,
                unit_price=4.50,
                total_price=450.00,
                batch_number="BATCH-01",
            )
        ],
        subtotal=450.00,
        tax_amount=54.00,
        total_amount=504.00,
    )


@pytest.fixture
def mock_client() -> MagicMock:
    """Fixture providing a mock SnowflakeClient with managed cursor context."""
    client = MagicMock(spec=SnowflakeClient)
    client.is_connected = True
    cursor_mock = MagicMock()
    # Mock context manager behavior for managed_cursor
    client.managed_cursor.return_value.__enter__.return_value = cursor_mock
    client.managed_cursor.return_value.__exit__.return_value = None
    return client


class TestBronzeInvoiceRepository:
    """Test suite for Snowflake Bronze invoice repository operations."""

    def test_get_insert_sql_styles(self) -> None:
        """Assert SQL generation matches qmark or pyformat placeholders."""
        sql_qmark = get_insert_sql("qmark")
        assert "PARSE_JSON(?)" in sql_qmark
        assert "SELECT ?, ?, CURRENT_TIMESTAMP(), PARSE_JSON(?)" in sql_qmark

        sql_pyformat = get_insert_sql("pyformat")
        assert "PARSE_JSON(%s)" in sql_pyformat
        assert "SELECT %s, %s, CURRENT_TIMESTAMP(), PARSE_JSON(%s)" in sql_pyformat

    def test_insert_pydantic_payload(
        self,
        mock_client: MagicMock,
        sample_payload: RawInvoicePayload,
    ) -> None:
        """Assert Pydantic model is serialized to JSON string and passed to cursor.execute."""
        repo = BronzeInvoiceRepository(client=mock_client)
        repo.insert_invoice(
            source_file="invoice_sample_01.pdf",
            partner_id="PARTNER_SP_01",
            payload=sample_payload,
            paramstyle="qmark",
        )

        cursor = mock_client.managed_cursor().__enter__()
        assert cursor.execute.call_count == 1
        query, params = cursor.execute.call_args[0]
        assert "PARSE_JSON(?)" in query
        assert params[0] == "invoice_sample_01.pdf"
        assert params[1] == "PARTNER_SP_01"

        # Verify 3rd param is valid JSON containing invoice fields
        payload_data = json.loads(params[2])
        assert payload_data["metadata"]["invoice_number"] == "INV-BRONZE-01"
        assert payload_data["total_amount"] == 504.00

    def test_insert_dict_payload(self, mock_client: MagicMock) -> None:
        """Assert raw dictionary payload is serialized properly."""
        repo = BronzeInvoiceRepository(client=mock_client)
        dict_payload = {"invoice_id": "123", "total": 99.90}

        repo.insert_invoice(
            source_file="raw_dict.json",
            partner_id="PARTNER_RJ_02",
            payload=dict_payload,
            paramstyle="pyformat",
        )

        cursor = mock_client.managed_cursor().__enter__()
        assert cursor.execute.call_count == 1
        query, params = cursor.execute.call_args[0]
        assert "PARSE_JSON(%s)" in query
        assert params[0] == "raw_dict.json"
        assert params[1] == "PARTNER_RJ_02"
        assert json.loads(params[2]) == dict_payload

    def test_batch_insert_invoices(
        self,
        mock_client: MagicMock,
        sample_payload: RawInvoicePayload,
    ) -> None:
        """Assert batch insertions iterate and persist each record."""
        repo = BronzeInvoiceRepository(client=mock_client)
        records = [
            ("file_1.pdf", "PARTNER_A", sample_payload),
            ("file_2.pdf", "PARTNER_B", {"custom": 1}),
        ]

        count = repo.batch_insert_invoices(records, paramstyle="qmark")
        assert count == 2
        cursor = mock_client.managed_cursor().__enter__()
        assert cursor.execute.call_count == 2

    def test_invalid_payload_type_raises(self, mock_client: MagicMock) -> None:
        """Assert non-Pydantic and non-dict payload raises TypeError."""
        repo = BronzeInvoiceRepository(client=mock_client)
        with pytest.raises(TypeError, match="Payload must be RawInvoicePayload or dict"):
            repo.insert_invoice(
                source_file="invalid.pdf",
                partner_id="PARTNER_INVALID",
                payload=12345,  # type: ignore[arg-type]
            )

    def test_context_manager_lifecycle(self) -> None:
        """Assert context manager invokes connect and close when owning connection."""
        client_mock = MagicMock(spec=SnowflakeClient)
        client_mock.is_connected = False

        repo = BronzeInvoiceRepository(client=client_mock)
        repo._owns_connection = True

        with repo:
            client_mock.connect.assert_called_once()

        client_mock.close.assert_called_once()
