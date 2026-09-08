# 🤖 AI-Ops, Agentic Architectures & Extraction Rules

- **Framework Architecture**:
  - Unstructured document parsing (e.g., partner B2B invoices) must utilize stateful, cyclic graphs built with LangGraph.
  - Separate document layout detection/OCR from schema validation and structured extraction nodes.
- **Strict Structured Outputs & Validation**:
  - Every LLM or heuristic extraction node MUST output data validated by Pydantic v2 schemas.
  - Implement self-correction feedback cycles in LangGraph: if validation fails, feedback the schema validation errors into the correction node before aborting.
- **Testing & Isolation Protocols**:
  - LLM API calls, embedding generators, and network calls MUST be fully mocked in automated unit and integration tests.
  - Provide synthetic sample documents (e.g., via ReportLab) and pre-computed golden JSON responses for deterministic test verification.
- **Observability & Tracing**:
  - All agent nodes and extraction chains must support metadata injection (run IDs, latency, token counts, model identifiers).
  - Persist extraction confidence scores and validation warning flags alongside raw payloads.
