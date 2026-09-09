"""Stateful cyclic LangGraph engine for B2B partner invoice parsing.

Implements an extraction and self-correction loop that parses raw invoice text,
validates against Pydantic v2 domain schemas, and loops back with structured
validation feedback on schema violations.
"""

import json
from collections.abc import Callable
from typing import Any, Literal, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from pydantic import ValidationError

from src.ingestion.models.invoice import RawInvoicePayload


class InvoiceParserState(TypedDict, total=False):
    """Execution state tracked across the LangGraph invoice parsing pipeline.

    Attributes:
        raw_text: Raw unparsed invoice text extracted from PDF.
        retry_count: Number of failed validation attempts so far.
        max_retries: Maximum permitted self-correction attempts (default 3).
        validation_errors: Descriptions of schema violations from the last attempt.
        candidate_data: Intermediate dictionary representation prior to model validation.
        parsed_payload: Fully validated RawInvoicePayload instance upon success.
        is_valid: Boolean indicating whether candidate payload passed all validations.
        status_message: Informational message tracking stage transitions.
    """

    raw_text: str
    retry_count: int
    max_retries: int
    validation_errors: list[str]
    candidate_data: dict[str, Any] | None
    parsed_payload: RawInvoicePayload | None
    is_valid: bool
    status_message: str


SYSTEM_PROMPT = """You are a specialized B2B Invoice Data Extraction Agent for Aura Energy Drink.
Your mission is to extract structured invoice data from unformatted text into JSON.

Requirements:
1. Target schema:
   - metadata: invoice_number (str), partner_id (str), partner_cnpj (str), issue_date (YYYY-MM-DD)
   - items: list of {sku, description, quantity, unit_price, total_price, batch_number}
   - subtotal: float
   - tax_amount: float (>= 0.0)
   - total_amount: float
2. Invariants:
   - partner_cnpj MUST be a valid 14-digit Brazilian CNPJ (with correct check digits).
   - Each item total_price MUST equal quantity * unit_price.
   - subtotal MUST equal the sum of item total_price values.
   - total_amount MUST equal subtotal + tax_amount.
3. Output strictly valid JSON with no extraneous commentary or markdown tags outside json blocks.
"""


def _clean_json_text(text: str) -> str:
    """Strip markdown code fence wrappers from LLM responses."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        start = 1 if lines[0].startswith("```") else 0
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        cleaned = "\n".join(lines[start:end]).strip()
    return cleaned


def create_extraction_node(
    llm: BaseChatModel | Callable[..., Any],
) -> Callable[[InvoiceParserState], dict[str, Any]]:
    """Build the LangGraph extraction node using the provided LLM or mock callable.

    Args:
        llm: Language model or callable mock providing structured extraction.

    Returns:
        Callable[[InvoiceParserState], dict[str, Any]]: State update node function.
    """

    def extract_node(state: InvoiceParserState) -> dict[str, Any]:
        raw_text = state.get("raw_text", "")
        errors = state.get("validation_errors", [])
        retry_count = state.get("retry_count", 0)

        messages: list[BaseMessage] = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"Extract the invoice payload from this document:\n\n{raw_text}"),
        ]

        if errors:
            feedback = (
                f"CORRECTION REQUEST (Attempt {retry_count}):\n"
                "Your previous extraction attempt failed with the following errors:\n"
                + "\n".join(f"- {e}" for e in errors)
                + "\nPlease recalculate and output corrected data strictly satisfying all rules."
            )
            messages.append(HumanMessage(content=feedback))

        try:
            if hasattr(llm, "invoke") and callable(llm.invoke):
                response = llm.invoke(messages)
            elif callable(llm):
                response = llm(messages)
            else:
                raise TypeError(f"LLM '{type(llm)}' must be callable or provide an invoke method")

            if isinstance(response, RawInvoicePayload):
                candidate_data = response.model_dump(mode="json")
            elif isinstance(response, dict):
                candidate_data = response
            elif isinstance(response, AIMessage):
                text_content = str(response.content)
                candidate_data = json.loads(_clean_json_text(text_content))
            elif isinstance(response, str):
                candidate_data = json.loads(_clean_json_text(response))
            else:
                candidate_data = json.loads(_clean_json_text(str(response)))

            return {
                "candidate_data": candidate_data,
                "status_message": f"Extraction executed (attempt {retry_count})",
            }
        except Exception as exc:
            return {
                "candidate_data": None,
                "validation_errors": [f"LLM extraction parse error: {exc}"],
                "status_message": f"Extraction error on attempt {retry_count}: {exc}",
            }

    return extract_node


def validate_invoice_node(state: InvoiceParserState) -> dict[str, Any]:
    """Validate extracted candidate data against RawInvoicePayload schema and invariants.

    Args:
        state: Active graph state containing candidate_data.

    Returns:
        dict[str, Any]: Updated state keys (is_valid, parsed_payload, validation_errors).
    """
    candidate = state.get("candidate_data")
    current_retries = state.get("retry_count", 0)

    if candidate is None:
        existing_errors = state.get("validation_errors") or ["No candidate data extracted"]
        return {
            "is_valid": False,
            "retry_count": current_retries + 1,
            "validation_errors": existing_errors,
            "status_message": f"Validation failed: No data extracted (retry {current_retries + 1})",
        }

    try:
        validated = RawInvoicePayload.model_validate(candidate)
        return {
            "is_valid": True,
            "parsed_payload": validated,
            "validation_errors": [],
            "status_message": "Payload passed schema and financial invariant validation",
        }
    except (ValidationError, ValueError) as err:
        errors = [str(err)]
        return {
            "is_valid": False,
            "retry_count": current_retries + 1,
            "validation_errors": errors,
            "status_message": f"Validation failed on retry {current_retries + 1}: {err}",
        }


def should_continue(state: InvoiceParserState) -> Literal["extract", "__end__"]:
    """Conditional routing edge determining whether to loop for correction or terminate.

    Args:
        state: Active state after validation node.

    Returns:
        Literal["extract", "__end__"]: Target node identifier or terminal END.
    """
    if state.get("is_valid", False):
        return END

    max_retries = state.get("max_retries", 3)
    retry_count = state.get("retry_count", 0)

    if retry_count >= max_retries:
        return END

    return "extract"


def create_invoice_graph(
    llm: BaseChatModel | Callable[..., Any] | None = None,
    max_retries: int = 3,
) -> StateGraph:
    """Compile and configure the LangGraph state machine for self-correcting invoice parsing.

    Args:
        llm: Language model or mock callable. Defaults to ChatOpenAI(temperature=0.0) if None.
        max_retries: Maximum self-correction attempts before termination.

    Returns:
        StateGraph: Compiled LangGraph runnable workflow.
    """
    if llm is None:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)

    workflow = StateGraph(InvoiceParserState)

    extract_fn = create_extraction_node(llm)
    workflow.add_node("extract", extract_fn)
    workflow.add_node("validate", validate_invoice_node)

    workflow.set_entry_point("extract")
    workflow.add_edge("extract", "validate")
    workflow.add_conditional_edges(
        "validate",
        should_continue,
        {
            "extract": "extract",
            END: END,
        },
    )

    return workflow.compile()


def parse_invoice_document(
    raw_text: str,
    llm: BaseChatModel | Callable[..., Any] | None = None,
    max_retries: int = 3,
) -> InvoiceParserState:
    """Parse raw invoice document text through the self-correcting LangGraph workflow.

    Args:
        raw_text: Text extracted from invoice document.
        llm: Optional language model or mock.
        max_retries: Maximum allowed self-correction retries.

    Returns:
        InvoiceParserState: Final workflow state including parsed_payload or validation errors.
    """
    graph = create_invoice_graph(llm=llm, max_retries=max_retries)
    initial_state: InvoiceParserState = {
        "raw_text": raw_text,
        "retry_count": 0,
        "max_retries": max_retries,
        "validation_errors": [],
        "candidate_data": None,
        "parsed_payload": None,
        "is_valid": False,
        "status_message": "Workflow started",
    }
    final_state = graph.invoke(initial_state)
    return final_state
