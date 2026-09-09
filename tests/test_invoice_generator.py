"""Unit tests for synthetic PDF invoice generator."""

from datetime import date
from pathlib import Path

import pytest
from pypdf import PdfReader

from src.ingestion.generators.invoice_generator import (
    AVAILABLE_LAYOUTS,
    LayoutType,
    generate_invoice_pdf,
    generate_sample_invoices,
)
from src.ingestion.models.invoice import (
    InvoiceItem,
    InvoiceMetadata,
    RawInvoicePayload,
)


@pytest.fixture
def sample_payload() -> RawInvoicePayload:
    """Fixture providing a standard valid RawInvoicePayload."""
    return RawInvoicePayload(
        metadata=InvoiceMetadata(
            invoice_number="INV-TEST-001",
            partner_id="PARTNER_DIST_SP_01",
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
                batch_number="BATCH-TEST-A1",
            ),
            InvoiceItem(
                sku="AURA_ZERO_250ML",
                description="Aura Zero Sugar Energy Drink 250ml",
                quantity=50,
                unit_price=4.80,
                total_price=240.00,
                batch_number="BATCH-TEST-Z1",
            ),
        ],
        subtotal=690.00,
        tax_amount=82.80,
        total_amount=772.80,
    )


class TestInvoiceGenerator:
    """Test suite for ReportLab PDF generator layouts."""

    @pytest.mark.parametrize("layout", AVAILABLE_LAYOUTS)
    def test_generate_pdf_layouts(
        self,
        sample_payload: RawInvoicePayload,
        layout: LayoutType,
        tmp_path: Path,
    ) -> None:
        """Assert valid PDF binary generation across all supported ERP layouts."""
        output_file = tmp_path / f"invoice_{layout}.pdf"
        result_path = generate_invoice_pdf(sample_payload, output_file, layout=layout)

        assert result_path.exists()
        assert result_path.is_file()
        assert result_path.stat().st_size > 0

        # Validate PDF header magic bytes
        header = result_path.read_bytes()[:5]
        assert header == b"%PDF-"

        # Verify readable with pypdf and contains SKUs and CNPJ
        reader = PdfReader(str(result_path))
        assert len(reader.pages) >= 1
        text_content = "".join(page.extract_text() or "" for page in reader.pages)
        assert "AURA_250ML" in text_content
        assert "00.000.000/0001-91" in text_content

    def test_unsupported_layout_rejected(
        self,
        sample_payload: RawInvoicePayload,
        tmp_path: Path,
    ) -> None:
        """Assert unsupported layout name raises ValueError."""
        output_file = tmp_path / "invalid.pdf"
        with pytest.raises(ValueError, match="Unsupported layout 'oracle_netsuite'"):
            generate_invoice_pdf(
                sample_payload,
                output_file,
                layout="oracle_netsuite",  # type: ignore[arg-type]
            )

    def test_generate_sample_invoices(self, tmp_path: Path) -> None:
        """Assert batch sample generator produces distinct valid invoice files."""
        generated = generate_sample_invoices(tmp_path, count=3)
        assert len(generated) == 3
        for pdf_path in generated:
            assert pdf_path.exists()
            assert pdf_path.stat().st_size > 0
            reader = PdfReader(str(pdf_path))
            assert len(reader.pages) >= 1
