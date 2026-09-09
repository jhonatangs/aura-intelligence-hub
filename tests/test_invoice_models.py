"""Unit tests for invoice domain models and Pydantic validation contracts."""

from datetime import date

import pytest
from pydantic import ValidationError

from src.ingestion.models.invoice import (
    InvoiceItem,
    InvoiceMetadata,
    RawInvoicePayload,
    validate_cnpj,
)


class TestCnpjValidation:
    """Test suite for Brazilian CNPJ validation logic."""

    def test_valid_formatted_cnpj(self) -> None:
        """Assert valid formatted CNPJ strings are accepted and preserved."""
        assert validate_cnpj("00.000.000/0001-91") == "00.000.000/0001-91"
        assert validate_cnpj("11.222.333/0001-81") == "11.222.333/0001-81"

    def test_valid_unformatted_cnpj(self) -> None:
        """Assert 14-digit unformatted strings are normalized to standard mask."""
        assert validate_cnpj("00000000000191") == "00.000.000/0001-91"
        assert validate_cnpj("11222333000181") == "11.222.333/0001-81"

    def test_invalid_cnpj_length(self) -> None:
        """Assert strings with non-14 digit count raise ValueError."""
        with pytest.raises(ValueError, match="must contain exactly 14 digits"):
            validate_cnpj("123456780001")

        with pytest.raises(ValueError, match="must contain exactly 14 digits"):
            validate_cnpj("12.345.678/0001-999")

    def test_repeated_identical_digits(self) -> None:
        """Assert repeated identical digits are rejected."""
        with pytest.raises(ValueError, match="identical repeated digits"):
            validate_cnpj("00.000.000/0000-00")
        with pytest.raises(ValueError, match="identical repeated digits"):
            validate_cnpj("11.111.111/1111-11")

    def test_invalid_first_checksum_digit(self) -> None:
        """Assert invalid first verification digit raises ValueError."""
        # Valid is 00.000.000/0001-91; mutate first digit to 8
        with pytest.raises(ValueError, match="first verification digit"):
            validate_cnpj("00.000.000/0001-81")

    def test_invalid_second_checksum_digit(self) -> None:
        """Assert invalid second verification digit raises ValueError."""
        # Valid is 00.000.000/0001-91; mutate second digit to 2
        with pytest.raises(ValueError, match="second verification digit"):
            validate_cnpj("00.000.000/0001-92")


class TestInvoiceItemValidation:
    """Test suite for InvoiceItem model constraints."""

    def test_valid_item(self) -> None:
        """Assert valid item passes validation."""
        item = InvoiceItem(
            sku="AURA_250ML",
            description="Aura Original Energy Drink 250ml",
            quantity=100,
            unit_price=4.50,
            total_price=450.00,
            batch_number="BATCH-2026-09-A",
        )
        assert item.sku == "AURA_250ML"
        assert item.quantity == 100
        assert item.total_price == 450.00

    def test_zero_or_negative_quantity(self) -> None:
        """Assert zero or negative quantity raises ValidationError."""
        with pytest.raises(ValidationError):
            InvoiceItem(
                sku="AURA_250ML",
                description="Aura Original",
                quantity=0,
                unit_price=4.50,
                total_price=0.00,
                batch_number="B1",
            )
        with pytest.raises(ValidationError):
            InvoiceItem(
                sku="AURA_250ML",
                description="Aura Original",
                quantity=-5,
                unit_price=4.50,
                total_price=-22.50,
                batch_number="B1",
            )

    def test_zero_or_negative_unit_price(self) -> None:
        """Assert non-positive unit price raises ValidationError."""
        with pytest.raises(ValidationError):
            InvoiceItem(
                sku="AURA_250ML",
                description="Aura Original",
                quantity=10,
                unit_price=0.0,
                total_price=0.0,
                batch_number="B1",
            )
        with pytest.raises(ValidationError):
            InvoiceItem(
                sku="AURA_250ML",
                description="Aura Original",
                quantity=10,
                unit_price=-2.0,
                total_price=-20.0,
                batch_number="B1",
            )

    def test_total_price_mismatch(self) -> None:
        """Assert discrepancy between quantity * unit_price and total_price is rejected."""
        with pytest.raises(ValidationError, match="does not match quantity \\* unit_price"):
            InvoiceItem(
                sku="AURA_250ML",
                description="Aura Original",
                quantity=10,
                unit_price=5.00,
                total_price=60.00,  # Expected 50.00
                batch_number="B1",
            )


class TestRawInvoicePayloadValidation:
    """Test suite for full invoice payload consistency."""

    @pytest.fixture
    def valid_metadata(self) -> InvoiceMetadata:
        """Provide a valid InvoiceMetadata fixture."""
        return InvoiceMetadata(
            invoice_number="NF-001928",
            partner_id="PARTNER_DIST_SP",
            partner_cnpj="00.000.000/0001-91",
            issue_date=date(2026, 9, 8),
        )

    @pytest.fixture
    def valid_items(self) -> list[InvoiceItem]:
        """Provide valid line items fixture."""
        return [
            InvoiceItem(
                sku="AURA_250ML",
                description="Aura Original 250ml",
                quantity=200,
                unit_price=4.00,
                total_price=800.00,
                batch_number="BATCH-A01",
            ),
            InvoiceItem(
                sku="AURA_ZERO_250ML",
                description="Aura Zero Sugar 250ml",
                quantity=100,
                unit_price=4.50,
                total_price=450.00,
                batch_number="BATCH-Z01",
            ),
        ]

    def test_valid_invoice_payload(
        self,
        valid_metadata: InvoiceMetadata,
        valid_items: list[InvoiceItem],
    ) -> None:
        """Assert valid invoice payload passes all invariant checks."""
        payload = RawInvoicePayload(
            metadata=valid_metadata,
            items=valid_items,
            subtotal=1250.00,
            tax_amount=150.00,
            total_amount=1400.00,
        )
        assert payload.subtotal == 1250.00
        assert payload.total_amount == 1400.00
        assert len(payload.items) == 2

    def test_empty_items_rejected(self, valid_metadata: InvoiceMetadata) -> None:
        """Assert payload with empty items list is rejected."""
        with pytest.raises(ValidationError):
            RawInvoicePayload(
                metadata=valid_metadata,
                items=[],
                subtotal=0.0,
                tax_amount=0.0,
                total_amount=0.0,
            )

    def test_subtotal_mismatch_rejected(
        self,
        valid_metadata: InvoiceMetadata,
        valid_items: list[InvoiceItem],
    ) -> None:
        """Assert subtotal not matching sum of item totals is rejected."""
        with pytest.raises(ValidationError, match="subtotal .* does not match sum of items"):
            RawInvoicePayload(
                metadata=valid_metadata,
                items=valid_items,
                subtotal=999.00,  # Actual is 1250.00
                tax_amount=150.00,
                total_amount=1149.00,
            )

    def test_total_amount_mismatch_rejected(
        self,
        valid_metadata: InvoiceMetadata,
        valid_items: list[InvoiceItem],
    ) -> None:
        """Assert total amount not matching subtotal + tax_amount is rejected."""
        with pytest.raises(ValidationError, match="total_amount .* does not match subtotal"):
            RawInvoicePayload(
                metadata=valid_metadata,
                items=valid_items,
                subtotal=1250.00,
                tax_amount=150.00,
                total_amount=1500.00,  # Expected 1400.00
            )

    def test_negative_tax_rejected(
        self,
        valid_metadata: InvoiceMetadata,
        valid_items: list[InvoiceItem],
    ) -> None:
        """Assert negative tax amount is rejected."""
        with pytest.raises(ValidationError):
            RawInvoicePayload(
                metadata=valid_metadata,
                items=valid_items,
                subtotal=1250.00,
                tax_amount=-10.00,
                total_amount=1240.00,
            )
