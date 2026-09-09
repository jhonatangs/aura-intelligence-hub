"""Unit tests for the invoice ingestion pipeline CLI."""

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.ingestion.models.invoice import (
    InvoiceItem,
    InvoiceMetadata,
    RawInvoicePayload,
)
from src.ingestion.pipelines.run_invoice_ingestion import run_pipeline


def _make_mock_payload() -> RawInvoicePayload:
    """Helper creating a sample RawInvoicePayload."""
    return RawInvoicePayload(
        metadata=InvoiceMetadata(
            invoice_number="INV-CLI-01",
            partner_id="PARTNER_CLI",
            partner_cnpj="00.000.000/0001-91",
            issue_date=date(2026, 9, 8),
        ),
        items=[
            InvoiceItem(
                sku="AURA_250ML",
                description="Aura Original",
                quantity=10,
                unit_price=4.00,
                total_price=40.00,
                batch_number="B-CLI",
            )
        ],
        subtotal=40.00,
        tax_amount=4.00,
        total_amount=44.00,
    )


class TestRunInvoiceIngestion:
    """Test suite for pipeline CLI execution."""

    @patch("src.ingestion.pipelines.run_invoice_ingestion.parse_invoice_document")
    def test_run_pipeline_dry_run(
        self,
        mock_parse: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Assert dry-run parses PDFs and terminates with exit code 0 without writing to DB."""
        mock_payload = _make_mock_payload()
        mock_parse.return_value = {
            "is_valid": True,
            "retry_count": 0,
            "parsed_payload": mock_payload,
            "validation_errors": [],
        }

        ret = run_pipeline(
            output_dir=tmp_path,
            generate_samples=2,
            dry_run=True,
        )

        assert ret == 0
        assert mock_parse.call_count == 2

    @patch("src.ingestion.pipelines.run_invoice_ingestion.BronzeInvoiceRepository")
    @patch("src.ingestion.pipelines.run_invoice_ingestion.parse_invoice_document")
    def test_run_pipeline_with_snowflake_insert(
        self,
        mock_parse: MagicMock,
        mock_repo_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Assert pipeline inserts successfully parsed records into Snowflake repository."""
        mock_repo = MagicMock()
        mock_repo_cls.return_value = mock_repo

        mock_payload = _make_mock_payload()
        mock_parse.return_value = {
            "is_valid": True,
            "retry_count": 0,
            "parsed_payload": mock_payload,
            "validation_errors": [],
        }

        ret = run_pipeline(
            output_dir=tmp_path,
            generate_samples=1,
            dry_run=False,
        )

        assert ret == 0
        assert mock_repo.insert_invoice.call_count == 1
        call_kwargs = mock_repo.insert_invoice.call_args[1]
        assert call_kwargs["partner_id"] == "PARTNER_CLI"
        assert call_kwargs["payload"] == mock_payload

    @patch("src.ingestion.pipelines.run_invoice_ingestion.parse_invoice_document")
    def test_run_pipeline_handles_parse_failure(
        self,
        mock_parse: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Assert pipeline records error and exits with code 1 when parsing fails."""
        mock_parse.return_value = {
            "is_valid": False,
            "retry_count": 3,
            "parsed_payload": None,
            "validation_errors": ["Invalid total amount"],
        }

        ret = run_pipeline(
            output_dir=tmp_path,
            generate_samples=1,
            dry_run=True,
        )

        assert ret == 1

    def test_run_pipeline_empty_directory(self, tmp_path: Path) -> None:
        """Assert empty folder without generation returns 0 with no action taken."""
        ret = run_pipeline(
            output_dir=tmp_path,
            skip_generation=True,
            dry_run=True,
        )
        assert ret == 0
