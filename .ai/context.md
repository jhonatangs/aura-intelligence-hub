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
    - **Pipeline**: Ingested and processed through a LangGraph cyclic stateful parser with Pydantic v2 structured validation and schema self-correction (`src/ingestion/agents/invoice_graph.py`).
    - **Target**: `AURA_LAKEHOUSE.BRONZE.INVOICES_RAW` (Snowflake `VARIANT` payload column with metadata columns `source_file`, `partner_id`, and `ingested_at`).
 
 2. **Competitor Pricing Intelligence**:
    - **Source**: High-frequency concurrent web scrapers monitoring e-commerce and retail distribution channels for Red Bull and Monster Energy (`src/ingestion/scrapers/competitor_scraper.py`).
    - **Target**: `AURA_LAKEHOUSE.BRONZE.COMPETITOR_PRICES_RAW` (`source_url`, `competitor_brand`, `ingested_at`, `payload VARIANT`).
    - **Repository**: `BronzeCompetitorPriceRepository` (`src/ingestion/repositories/bronze_competitor_repo.py`).
 
 3. **Macro Climatic Context**:
    - **Source**: Open-Meteo REST API delivering historical and forecasted daily weather metrics (maximum temperature, precipitation levels) across 10 distribution hubs (SP, RJ, BH, Curitiba, Porto Alegre, Salvador, Recife, Fortaleza, Goiânia, Cuiabá) via `OpenMeteoClient` (`src/ingestion/clients/weather_client.py`).
    - **Target**: `AURA_LAKEHOUSE.BRONZE.WEATHER_METRICS_RAW` (`city_hub`, `state`, `ingested_at`, `payload VARIANT`).
    - **Repository**: `BronzeWeatherRepository` (`src/ingestion/repositories/bronze_weather_repo.py`).
 
 4. **Legacy Partner Warehouse Inventories**:
    - **Source**: Delimited tabular files (CSV, TXT with variable delimiters `;`, `,`, `|`, and Latin-1/UTF-8 encodings) extracted from legacy ERPs and regional partner warehouse systems, parsed with MD5 deduplication hash tracking (`src/ingestion/parsers/tabular_inventory.py`).
    - **Target**: `AURA_LAKEHOUSE.BRONZE.PARTNER_INVENTORY_RAW` (`source_file`, `partner_id`, `file_hash_md5`, `ingested_at`, `payload VARIANT`).
    - **Repository**: `BronzePartnerInventoryRepository` (`src/ingestion/repositories/bronze_inventory_repo.py`).
 
 ---
 
 ## 3. Architecture & Infrastructure
 
 - **Package & Dependency Management**: Python 3.11+ managed deterministically via `uv` adhering strictly to PEP 621 (`pyproject.toml` and lockfile `uv.lock`). Dependencies include `httpx`, `beautifulsoup4`, `tenacity`, `dagster`, `reportlab`, `pypdf`, `langgraph`, `pydantic`.
 - **Data Lakehouse**: Snowflake Medallion Lakehouse (`BRONZE` -> `SILVER` -> `GOLD`).
   - **IaC**: Idempotent SQL scripts (`scripts/init_snowflake.sql`) defining warehouse `COMPUTE_WH` (`X-SMALL`, initially suspended, auto-suspend 60 seconds, auto-resume true), database `AURA_LAKEHOUSE`, schemas `BRONZE`, `SILVER`, `GOLD`, and table structures.
   - **Authentication**: Enterprise-grade RSA 2048-bit PKCS#8 key-pair authentication without plain-text passwords.
 - **Orchestration**: Dagster Software-Defined Assets (SDAs) in `src/orchestration/assets/bronze.py` (`bronze_invoices_raw`, `bronze_weather_metrics_raw`, `bronze_competitor_prices_raw`, `bronze_partner_inventory_raw`) and registered definitions in `src/orchestration/definitions.py`.
 - **Quality & Governance**: Strict typing, Ruff formatting/linting (100% compliant), and unit test suites isolated with mocks and fixtures (110 tests passing, 0 live network/db leaks).
