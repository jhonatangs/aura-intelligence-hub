"""Unit tests for LangGraph self-correcting invoice parser agent."""

from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from src.ingestion.agents.invoice_graph import parse_invoice_document
from src.ingestion.models.invoice import RawInvoicePayload

VALID_JSON_RESPONSE = """{
  "metadata": {
    "invoice_number": "INV-MOCK-101",
    "partner_id": "PARTNER_SP_01",
    "partner_cnpj": "00.000.000/0001-91",
    "issue_date": "2026-09-08"
  },
  "items": [
    {
      "sku": "AURA_250ML",
      "description": "Aura Original 250ml",
      "quantity": 100,
      "unit_price": 4.50,
      "total_price": 450.00,
      "batch_number": "BATCH-001"
    }
  ],
  "subtotal": 450.00,
  "tax_amount": 54.00,
  "total_amount": 504.00
}"""

# Deliberate math violation: total_amount (999.00) != subtotal (450.00) + tax (54.00)
INVALID_MATH_JSON_RESPONSE = """{
  "metadata": {
    "invoice_number": "INV-MOCK-101",
    "partner_id": "PARTNER_SP_01",
    "partner_cnpj": "00.000.000/0001-91",
    "issue_date": "2026-09-08"
  },
  "items": [
    {
      "sku": "AURA_250ML",
      "description": "Aura Original 250ml",
      "quantity": 100,
      "unit_price": 4.50,
      "total_price": 450.00,
      "batch_number": "BATCH-001"
    }
  ],
  "subtotal": 450.00,
  "tax_amount": 54.00,
  "total_amount": 999.00
}"""


class TestInvoiceGraph:
    """Test suite for LangGraph cyclic parser and error recovery."""

    def test_single_pass_extraction_success(self) -> None:
        """Assert valid output on first attempt terminates immediately with is_valid=True."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content=VALID_JSON_RESPONSE)

        result = parse_invoice_document(
            raw_text="Sample raw invoice text",
            llm=mock_llm,
            max_retries=3,
        )

        assert result["is_valid"] is True
        assert result["retry_count"] == 0
        assert isinstance(result["parsed_payload"], RawInvoicePayload)
        assert result["parsed_payload"].metadata.invoice_number == "INV-MOCK-101"
        assert result["parsed_payload"].total_amount == 504.00
        assert mock_llm.invoke.call_count == 1

    def test_cyclic_self_correction_recovery(self) -> None:
        """Assert cyclic feedback loop triggers correction prompt and recovers on retry."""
        mock_llm = MagicMock()
        # First attempt produces invalid math; second attempt returns corrected payload
        mock_llm.invoke.side_effect = [
            AIMessage(content=INVALID_MATH_JSON_RESPONSE),
            AIMessage(content=VALID_JSON_RESPONSE),
        ]

        result = parse_invoice_document(
            raw_text="Sample raw invoice text requiring correction",
            llm=mock_llm,
            max_retries=3,
        )

        assert result["is_valid"] is True
        assert result["retry_count"] == 1
        assert isinstance(result["parsed_payload"], RawInvoicePayload)
        assert mock_llm.invoke.call_count == 2

        # Verify second call included correction feedback in messages
        second_call_messages = mock_llm.invoke.call_args_list[1][0][0]
        correction_msgs = [m for m in second_call_messages if "CORRECTION REQUEST" in m.content]
        assert len(correction_msgs) == 1
        assert "total_amount" in correction_msgs[0].content

    def test_max_retries_graceful_termination(self) -> None:
        """Assert loop terminates gracefully without unhandled exception when retries exhaust."""
        mock_llm = MagicMock()
        # Returns invalid payload constantly
        mock_llm.invoke.return_value = AIMessage(content=INVALID_MATH_JSON_RESPONSE)

        result = parse_invoice_document(
            raw_text="Corrupt invoice text",
            llm=mock_llm,
            max_retries=2,
        )

        assert result["is_valid"] is False
        assert result["retry_count"] == 2
        assert result["parsed_payload"] is None
        assert len(result["validation_errors"]) > 0
        assert mock_llm.invoke.call_count == 2

    def test_malformed_json_resilience(self) -> None:
        """Assert non-JSON LLM text output is caught and routed through retry loop."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            AIMessage(content="Sorry, I cannot parse this document."),
            AIMessage(content=VALID_JSON_RESPONSE),
        ]

        result = parse_invoice_document(
            raw_text="Document text",
            llm=mock_llm,
            max_retries=3,
        )

        assert result["is_valid"] is True
        assert result["retry_count"] == 1
        assert isinstance(result["parsed_payload"], RawInvoicePayload)
        assert mock_llm.invoke.call_count == 2
