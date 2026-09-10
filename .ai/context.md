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

 ## 3. Silver Layer Transformations (Conformed Relational Layer)

 Pushdown idempotent SQL transformations leveraging Snowflake `MERGE` with `QUALIFY ROW_NUMBER() OVER (...) = 1` for deduplication and schema conformation:
 1. **`AURA_LAKEHOUSE.SILVER.INVOICES`**:
    - Deduplicated invoice headers (`invoice_number`, `partner_id`, `partner_cnpj`, `issue_date`, `subtotal`, `tax_amount`, `total_amount`, `source_file`, `ingested_at`, `transformed_at`).
 2. **`AURA_LAKEHOUSE.SILVER.INVOICE_ITEMS`**:
    - Flattened line items via `LATERAL FLATTEN(INPUT => payload:items)` (`invoice_number`, `partner_id`, `sku`, `description`, `quantity`, `unit_price`, `total_price`, `batch_number`, `source_file`, `transformed_at`).
 3. **`AURA_LAKEHOUSE.SILVER.COMPETITOR_PRICES`**:
    - Cleansed competitor price observations for Red Bull and Monster (`competitor_brand`, `product_title`, `volume_ml`, `price_brl`, `stock_status`, `observed_at`, `source_url`, `transformed_at`).
 4. **`AURA_LAKEHOUSE.SILVER.WEATHER_METRICS`**:
    - Conformed daily meteorological metrics per distribution hub (`city_hub`, `state`, `metric_date`, `temp_max`, `temp_min`, `precipitation_sum`, `transformed_at`).
 5. **`AURA_LAKEHOUSE.SILVER.PARTNER_INVENTORY`**:
    - Deduplicated inventory balances (`partner_id`, `sku`, `batch_id`, `stock_quantity`, `warehouse_location`, `snapshot_date`, `file_hash_md5`, `source_file`, `transformed_at`).

 Transformation modules:
 - Query builder: `src/transformation/sql/silver_transforms.py`
 - Service layer: `SilverTransformationService` (`src/transformation/services/silver_service.py`)
 - Pipeline CLI: `src/transformation/pipelines/run_silver_transforms.py`

 ---

 ## 4. Gold Layer Dimensional Modeling (Kimball Star Schema) & Analytical Marts

 Curated dimensional star schema and analytical marts powered by pushdown Snowflake MERGE statements executed in strict topological dependency order (Dimensions first, then Facts):

 1. **Dimensions**:
    - **`AURA_LAKEHOUSE.GOLD.DIM_DATE`**: Deterministic 5-year calendar date spine (2023–2027) generated via Snowflake `GENERATOR(ROWCOUNT => 1826)` with temporal keys, day of week/month, quarter, year, and weekend flags (`date_key` NUMBER(8,0) YYYYMMDD).
    - **`AURA_LAKEHOUSE.GOLD.DIM_PARTNERS`**: Conformed distributor dimension combining distinct partners from `SILVER.INVOICES` and `SILVER.PARTNER_INVENTORY` with `MD5(partner_id)` surrogate keys (`partner_key`, `partner_id`, `partner_cnpj`, `partner_name`, `channel_type`, `first_seen_date`, `last_active_date`, `is_active`).
    - **`AURA_LAKEHOUSE.GOLD.DIM_SKUS`**: Conformed SKU catalog mapping Aura products (`AURA_250ML`, `AURA_ZERO_250ML`, `AURA_TROPICAL_473ML`) with `MD5(sku)` surrogate keys, product names, volume in ml, flavor, package type (`CAN`), and category (`ENERGY_DRINK`).
    - **`AURA_LAKEHOUSE.GOLD.DIM_HUBS`**: Regional logistics hubs dimension seeded from the centralized `DISTRIBUTION_HUBS` registry (`hub_key` MD5, `hub_id`, `hub_name`, `city`, `state`, `latitude`, `longitude`, `timezone`).

 2. **Facts**:
    - **`AURA_LAKEHOUSE.GOLD.FACT_SELLOUT`**: Granular transactional fact table resolving foreign keys for date, partner, and SKU, tracking line-item quantities sold, unit prices, total prices, allocated tax amounts, and net revenues (`sellout_key` MD5 hash, `date_key`, `partner_key`, `sku_key`, `invoice_number`, `batch_number`, `quantity_sold`, `unit_price`, `total_price`, `tax_amount`, `net_revenue`).
    - **`AURA_LAKEHOUSE.GOLD.FACT_INVENTORY_SNAPSHOT`**: Periodic warehouse inventory snapshot fact resolving partner, SKU, and date dimension keys (`snapshot_key` MD5 hash, `date_key`, `partner_key`, `sku_key`, `batch_id`, `warehouse_location`, `stock_quantity`, `snapshot_date`).
    - **`AURA_LAKEHOUSE.GOLD.FACT_COMPETITOR_PRICING`**: Competitor pricing intelligence fact computing price-per-ml and normalizing stock status flags (`pricing_key` MD5 hash, `date_key`, `competitor_brand`, `product_title`, `volume_ml`, `price_brl`, `price_per_ml`, `stock_status`, `is_in_stock`, `observed_at`, `source_url`).

 3. **Analytical Mart Views**:
    - **`AURA_LAKEHOUSE.GOLD.V_MARKET_INTELLIGENCE_AUDIT`**: Unified analytical audit view joining `FACT_SELLOUT` with `DIM_DATE`, `DIM_PARTNERS`, `DIM_SKUS`, `FACT_INVENTORY_SNAPSHOT`, and `SILVER.WEATHER_METRICS` to audit B2B sell-out volumes, calculate revenue leakage, compare price per ml, correlate stock levels, and evaluate climatic demand drivers.

 Dimensional modules:
 - Query builder: `src/transformation/sql/gold_transforms.py`
 - Service layer: `GoldTransformationService` (`src/transformation/services/gold_service.py`)
 - Pipeline CLI: `src/transformation/pipelines/run_gold_transforms.py`

 ---

 ## 5. Architecture & Infrastructure

 - **Package & Dependency Management**: Python 3.11+ managed deterministically via `uv` adhering strictly to PEP 621 (`pyproject.toml` and lockfile `uv.lock`). Dependencies include `httpx`, `beautifulsoup4`, `tenacity`, `dagster`, `reportlab`, `pypdf`, `langgraph`, `pydantic`.
 - **Data Lakehouse**: Snowflake Medallion Lakehouse (`BRONZE` -> `SILVER` -> `GOLD`).
   - **IaC**: Idempotent SQL scripts (`scripts/init_snowflake.sql`) defining warehouse `COMPUTE_WH` (`X-SMALL`, initially suspended, auto-suspend 60 seconds, auto-resume true), database `AURA_LAKEHOUSE`, schemas `BRONZE`, `SILVER`, `GOLD`, tables, and analytical views.
   - **Authentication**: Enterprise-grade RSA 2048-bit PKCS#8 key-pair authentication without plain-text passwords.
 - **Orchestration**: Dagster Software-Defined Assets (SDAs):
   - Bronze layer: `src/orchestration/assets/bronze.py` (`bronze_invoices_raw`, `bronze_weather_metrics_raw`, `bronze_competitor_prices_raw`, `bronze_partner_inventory_raw`).
   - Silver layer: `src/orchestration/assets/silver.py` (`silver_invoices`, `silver_invoice_items`, `silver_competitor_prices`, `silver_weather_metrics`, `silver_partner_inventory`).
   - Gold layer: `src/orchestration/assets/gold.py` (`gold_dim_date`, `gold_dim_partners`, `gold_dim_skus`, `gold_dim_hubs`, `gold_fact_sellout`, `gold_fact_inventory_snapshot`, `gold_fact_competitor_pricing`).
   - Registered definitions in `src/orchestration/definitions.py`.
 - **Quality & Governance**: Strict typing, Ruff formatting/linting (100% compliant), and unit test suites isolated with mocks and fixtures (179 tests passing, 0 live network/db leaks).


