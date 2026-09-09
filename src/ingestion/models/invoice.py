"""Invoice domain schema models with Pydantic v2 validation.

Provides strongly typed data contracts for partner B2B invoices, including
Brazilian CNPJ checksum verification, item quantity/monetary consistency,
and overall invoice financial invariants.
"""

import re
from datetime import date
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def validate_cnpj(cnpj_raw: str) -> str:
    """Validate a Brazilian National Registry of Legal Entities (CNPJ) number.

    Validates both formatting and the official 2-digit verification algorithm.
    Accepts formatted ('XX.XXX.XXX/XXXX-XX') or numeric-only ('14 digits') strings.

    Args:
        cnpj_raw: Raw CNPJ string input.

    Returns:
        str: Formatted CNPJ string ('XX.XXX.XXX/XXXX-XX').

    Raises:
        ValueError: If the CNPJ string is malformed or fails mathematical checksums.
    """
    cleaned = re.sub(r"\D", "", cnpj_raw)
    if len(cleaned) != 14:
        raise ValueError(f"CNPJ must contain exactly 14 digits, got {len(cleaned)}: '{cnpj_raw}'")

    if len(set(cleaned)) == 1:
        raise ValueError(f"CNPJ cannot consist of identical repeated digits: '{cnpj_raw}'")

    weights_first = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    sum_first = sum(int(d) * w for d, w in zip(cleaned[:12], weights_first, strict=True))
    remainder_first = sum_first % 11
    digit1 = 0 if remainder_first < 2 else 11 - remainder_first

    if int(cleaned[12]) != digit1:
        raise ValueError(f"Invalid CNPJ first verification digit for '{cnpj_raw}'")

    weights_second = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    sum_second = sum(int(d) * w for d, w in zip(cleaned[:13], weights_second, strict=True))
    remainder_second = sum_second % 11
    digit2 = 0 if remainder_second < 2 else 11 - remainder_second

    if int(cleaned[13]) != digit2:
        raise ValueError(f"Invalid CNPJ second verification digit for '{cnpj_raw}'")

    return f"{cleaned[:2]}.{cleaned[2:5]}.{cleaned[5:8]}/{cleaned[8:12]}-{cleaned[12:14]}"


class InvoiceItem(BaseModel):
    """Line item within a B2B partner invoice.

    Attributes:
        sku: Stock Keeping Unit identifier (e.g., AURA_250ML, AURA_ZERO_250ML).
        description: Readable product description.
        quantity: Quantity of units sold, must be positive.
        unit_price: Unit selling price in BRL, must be positive.
        total_price: Total monetary line price, must match quantity * unit_price.
        batch_number: Manufacturing batch identification.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    sku: str = Field(..., min_length=1, description="Product SKU code")
    description: str = Field(..., min_length=1, description="Product description")
    quantity: int = Field(..., gt=0, description="Quantity sold")
    unit_price: float = Field(..., gt=0.0, description="Unit price in BRL")
    total_price: float = Field(..., gt=0.0, description="Total price for line item")
    batch_number: str = Field(..., min_length=1, description="Production batch ID")

    @model_validator(mode="after")
    def validate_item_total(self) -> Self:
        """Validate mathematical consistency between quantity, unit_price, and total_price.

        Returns:
            Self: Validated model instance.

        Raises:
            ValueError: If total_price does not match quantity * unit_price.
        """
        expected_total = round(self.quantity * self.unit_price, 2)
        if abs(expected_total - round(self.total_price, 2)) >= 0.01:
            raise ValueError(
                f"Line item total_price ({self.total_price}) does not match "
                f"quantity * unit_price ({self.quantity} * {self.unit_price} = {expected_total})"
            )
        return self


class InvoiceMetadata(BaseModel):
    """Metadata attributes identifying the invoice and partner.

    Attributes:
        invoice_number: Unique fiscal or ERP document number.
        partner_id: Internal partner or distributor code.
        partner_cnpj: Brazilian CNPJ identifying the partner entity.
        issue_date: Fiscal issue date.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    invoice_number: str = Field(..., min_length=1, description="Invoice document number")
    partner_id: str = Field(..., min_length=1, description="Partner organization identifier")
    partner_cnpj: str = Field(..., description="Brazilian CNPJ of issuing partner")
    issue_date: date = Field(..., description="Invoice issue date")

    @field_validator("partner_cnpj")
    @classmethod
    def check_cnpj(cls, v: str) -> str:
        """Validate partner CNPJ checksum and format."""
        return validate_cnpj(v)


class RawInvoicePayload(BaseModel):
    """Comprehensive structured invoice schema contract.

    Attributes:
        metadata: Header and partner identification metadata.
        items: Non-empty list of invoice line items.
        subtotal: Sum of item total prices.
        tax_amount: Associated taxes (ICMS/IPI/PIS/COFINS), must be non-negative.
        total_amount: Grand total (subtotal + tax_amount).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    metadata: InvoiceMetadata = Field(..., description="Invoice header metadata")
    items: list[InvoiceItem] = Field(..., min_length=1, description="List of invoiced items")
    subtotal: float = Field(..., gt=0.0, description="Sum of line item totals")
    tax_amount: float = Field(default=0.0, ge=0.0, description="Total applicable tax amount")
    total_amount: float = Field(..., gt=0.0, description="Grand total amount")

    @model_validator(mode="after")
    def validate_totals(self) -> Self:
        """Verify strict financial invariant formulas for the invoice.

        Returns:
            Self: Validated model instance.

        Raises:
            ValueError: If subtotal != sum(items) or total_amount != subtotal + tax_amount.
        """
        calculated_subtotal = round(sum(item.total_price for item in self.items), 2)
        if abs(calculated_subtotal - round(self.subtotal, 2)) >= 0.01:
            raise ValueError(
                f"Invoice subtotal ({self.subtotal}) does not match "
                f"sum of items ({calculated_subtotal})"
            )

        expected_total = round(self.subtotal + self.tax_amount, 2)
        if abs(expected_total - round(self.total_amount, 2)) >= 0.01:
            raise ValueError(
                f"Invoice total_amount ({self.total_amount}) does not match subtotal + tax_amount "
                f"({self.subtotal} + {self.tax_amount} = {expected_total})"
            )

        return self
