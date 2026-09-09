"""Unit tests for layout-preserving PDF reader and extraction error boundaries."""

from datetime import date
from pathlib import Path

import pytest

from src.ingestion.generators.invoice_generator import generate_invoice_pdf
from src.ingestion.models.invoice import (
    InvoiceItem,
    InvoiceMetadata,
    RawInvoicePayload,
)
from src.ingestion.parsers.pdf_reader import (
    PdfExtractionError,
    extract_pdf_document,
    extract_pdf_text,
)


@pytest.fixture
def sample_pdf_path(tmp_path: Path) -> Path:
    """Generate a valid sample PDF document for extraction testing."""
    payload = RawInvoicePayload(
        metadata=InvoiceMetadata(
            invoice_number="PDF-EXTRACT-01",
            partner_id="PARTNER_EXTRACT",
            partner_cnpj="00.000.000/0001-91",
            issue_date=date(2026, 9, 8),
        ),
        items=[
            InvoiceItem(
                sku="AURA_TROPICAL_473ML",
                description="Aura Tropical 473ml",
                quantity=150,
                unit_price=6.00,
                total_price=900.00,
                batch_number="BATCH-EXT-01",
            )
        ],
        subtotal=900.00,
        tax_amount=108.00,
        total_amount=1008.00,
    )
    target = tmp_path / "valid_sample.pdf"
    generate_invoice_pdf(payload, target, layout="enterprise_sap")
    return target


class TestPdfReader:
    """Test suite for PDF reader extraction and error boundaries."""

    def test_extract_pdf_document_success(self, sample_pdf_path: Path) -> None:
        """Assert valid PDF extraction returns structured document content."""
        doc = extract_pdf_document(sample_pdf_path)
        assert doc.page_count >= 1
        assert doc.file_path == str(sample_pdf_path)
        assert "AURA_TROPICAL_473ML" in doc.raw_text
        assert "00.000.000/0001-91" in doc.raw_text
        assert len(doc.tokens) > 10

        convenience_text = extract_pdf_text(sample_pdf_path)
        assert convenience_text == doc.raw_text

    def test_extract_pdf_missing_file(self, tmp_path: Path) -> None:
        """Assert non-existent file raises FileNotFoundError."""
        missing = tmp_path / "does_not_exist.pdf"
        with pytest.raises(FileNotFoundError):
            extract_pdf_document(missing)

    def test_extract_pdf_empty_file(self, tmp_path: Path) -> None:
        """Assert 0-byte file raises PdfExtractionError."""
        empty_file = tmp_path / "empty.pdf"
        empty_file.touch()
        with pytest.raises(PdfExtractionError, match="empty \\(0 bytes\\)"):
            extract_pdf_document(empty_file)

    def test_extract_pdf_corrupt_file(self, tmp_path: Path) -> None:
        """Assert invalid binary contents raise PdfExtractionError."""
        corrupt_file = tmp_path / "corrupt.pdf"
        corrupt_file.write_bytes(b"NOT A REAL PDF FILE CONTENT AT ALL")
        with pytest.raises(PdfExtractionError, match="Corrupted or invalid PDF document"):
            extract_pdf_document(corrupt_file)

    def test_extract_pdf_directory_target(self, tmp_path: Path) -> None:
        """Assert directory path target raises PdfExtractionError."""
        with pytest.raises(PdfExtractionError, match="Target path is not a file"):
            extract_pdf_document(tmp_path)
