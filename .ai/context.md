# 🧠 Project Context: Aura Intelligence Hub

## 1. Domain & Business Scope
Aura Intelligence Hub is an enterprise data lakehouse and competitive intelligence platform designed for **Aura Energy Drink**. The platform performs supply chain audits, partner sell-out reconciliation, and competitive benchmarking against market leaders **Red Bull** and **Monster Energy**.

Key objectives:
- Audit partner B2B sell-out volumes and identify revenue leakage.
- Benchmark pricing dynamics, retail promotions, and SKU positioning against Red Bull and Monster Energy across key metropolitan regions.
- Correlate consumption spikes and inventory depletion rates with macro-environmental factors (climatic and seasonal temperature shifts).
- Ensure seamless ingestion of heterogeneous data from partner ecosystems.

---

## 2. Ingestion Topologies

1. **Partner B2B Invoices (Sell-Out Analytics)**:
   - **Source**: Synthetic/unstructured partner invoice PDFs generated via ReportLab.
   - **Pipeline**: Ingested and processed through a LangGraph cyclic stateful parser with Pydantic v2 structured validation and schema self-correction.
   - **Target**: `AURA_LAKEHOUSE.BRONZE.INVOICES_RAW` (Snowflake `VARIANT` payload column with metadata columns `source_file`, `partner_id`, and `ingested_at`).

2. **Competitor Pricing Intelligence**:
   - **Source**: High-frequency concurrent web scrapers monitoring e-commerce and retail distribution channels for Red Bull and Monster Energy.
   - **Target**: `AURA_LAKEHOUSE.BRONZE.COMPETITOR_PRICES_RAW`.

3. **Macro Climatic Context**:
   - **Source**: Open-Meteo REST API delivering historical and forecasted daily weather metrics (maximum temperature, precipitation levels) across primary consumer hubs (São Paulo - SP, Rio de Janeiro - RJ, Belo Horizonte - MG).
   - **Target**: `AURA_LAKEHOUSE.BRONZE.WEATHER_METRICS_RAW`.

4. **Legacy Partner Warehouse Inventories**:
   - **Source**: Delimited tabular files (CSV, TXT with variable delimiters `;`, `,`, `|`) extracted from legacy ERPs and regional partner warehouse systems.
   - **Target**: `AURA_LAKEHOUSE.BRONZE.PARTNER_INVENTORY_RAW`.

---

## 3. Architecture & Infrastructure

- **Package & Dependency Management**: Python 3.11+ managed deterministically via `uv` adhering strictly to PEP 621 (`pyproject.toml` and lockfile `uv.lock`).
- **Data Lakehouse**: Snowflake Medallion Lakehouse (`BRONZE` -> `SILVER` -> `GOLD`).
  - **IaC**: Idempotent SQL scripts (`scripts/init_snowflake.sql`) defining warehouse `COMPUTE_WH` (`X-SMALL`, initially suspended, auto-suspend 60 seconds, auto-resume true), database `AURA_LAKEHOUSE`, schemas `BRONZE`, `SILVER`, `GOLD`, and table structures.
  - **Authentication**: Enterprise-grade RSA 2048-bit PKCS#8 key-pair authentication without plain-text passwords.
- **Orchestration**: Dagster Software-Defined Assets (SDAs) orchestrating idempotent end-to-end data pipelines, lineage tracking, and observability.
- **Quality & Governance**: Strict typing (`mypy` compliant), Ruff formatting/linting, and unit test suites isolated with mocks and fixtures.
