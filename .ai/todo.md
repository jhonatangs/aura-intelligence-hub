# 📋 Backlog & Tasks

Use this file to guide the autonomous agent. The agent must change the status from [ ] to [x] ONLY when the pipeline passes and the task is fully documented in the handoff state.

# Sprint 1: Bootstrap, Governance, RSA Key-Pair Config & Snowflake IaC

- [x] Task 1: Initialize Git and update `.gitignore` ensuring strict exclusion of `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.ruff_cache/`, `.env`, `data/raw/`, `*.db`, and cryptographical artifacts (`*.p8`, `*.pem`, `*.pub`).
- [x] Task 2: Create governance documentation under `.ai/rules/` (`01-global.md`, `02-python.md`, `03-data.md`, `04-ai-ops.md`, `05-frontend.md`) defining PEP 621 conventions, Ruff standards, deterministic type hints, and isolated mock-testing protocols.
- [x] Task 3: Author comprehensive domain context file at `.ai/context.md` covering:
  - Domain & Business Scope: Aura Energy Drink competitive intelligence and supply chain audit against Red Bull and Monster Energy.
  - Ingestion Topologies:
    1. Partner B2B Invoices (Sell-Out): Synthetic PDFs via ReportLab -> LangGraph cyclic stateful parser with Pydantic v2 validation -> `AURA_LAKEHOUSE.BRONZE.INVOICES_RAW` (VARIANT payload).
    2. Competitor Pricing Intelligence: Concurrent scraper for Red Bull and Monster -> `BRONZE.COMPETITOR_PRICES_RAW`.
    3. Macro Climatic Context: Open-Meteo REST API (daily max temp & precipitation for SP, RJ, BH) -> `BRONZE.WEATHER_METRICS_RAW`.
    4. Legacy Partner Warehouse Inventories: Delimited tabular files (CSV/TXT with `;`, `,`, `|`) -> `BRONZE.PARTNER_INVENTORY_RAW`.
  - Architecture & Infrastructure: `uv` package manager with `pyproject.toml` (PEP 621), Snowflake Medallion Lakehouse with idempotent SQL IaC (`COMPUTE_WH` X-SMALL, suspended, auto-suspend 60s), and Dagster Software-Defined Assets (SDAs).
- [x] Task 4: Provision repository folder layout creating `src/common`, `src/ingestion`, `src/transformation`, `src/orchestration`, `tests/`, `scripts/`, and `data/raw/partners/` with respective `__init__.py` module descriptors.
- [x] Task 5: Configure `pyproject.toml` targeting Python 3.11+ with `[tool.ruff]` (lint rules: E, F, I, UP, B, line-length 100) and `[tool.pytest.ini_options]` (`pythonpath = ["src"]` and standard test discovery).
- [x] Task 6: Create `.env.example` declaring required connection parameters using RSA key-pair authentication (`SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PRIVATE_KEY_PATH`, `SNOWFLAKE_PRIVATE_KEY_PASSPHRASE`, `SNOWFLAKE_ROLE`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`, `SNOWFLAKE_SCHEMA`), omitting any plain-text password variables.
- [x] Task 7: Implement immutable configuration model in `src/common/config.py` using `pydantic_settings.BaseSettings`, validating environment parameters, path existence for the private key file, and exposing typed properties.
- [x] Task 8: Author idempotent Snowflake SQL provisioning script at `scripts/init_snowflake.sql` defining warehouse `COMPUTE_WH` (size X-SMALL, auto-suspend 60, auto-resume true, initially suspended), database `AURA_LAKEHOUSE`, schemas `BRONZE`, `SILVER`, `GOLD`, and the raw ingestion table `BRONZE.INVOICES_RAW` with ingestion metadata (`source_file`, `partner_id`, `ingested_at`) and a `VARIANT` payload column.
- [x] Task 9: Implement enterprise Snowflake connection client in `src/common/snowflake_client.py` using a Python Context Manager (`__enter__` and `__exit__`), using `cryptography` to deserialize the PKCS#8 private key and converting it to DER format for `snowflake.connector.connect`.
- [x] Task 10: Author Python bootstrapping script at `scripts/bootstrap_snowflake.py` to parse and execute statements sequentially from `scripts/init_snowflake.sql` using the context-managed Snowflake client.
- [x] Task 11: Author unit tests in `tests/test_config.py` using `monkeypatch` and `tmp_path` to validate successful configuration loading, proper error handling for missing files, and rejection of invalid private key paths.
- [x] Task 12: Author unit tests in `tests/test_snowflake_client.py` mocking `cryptography.hazmat.primitives.serialization.load_pem_private_key` and `snowflake.connector.connect` to verify private key loading, DER serialization, connection parameters, cursor lifecycle, and deterministic cleanup on execution errors.
- [x] Task 13: Run quality gate verification commands (`uv run ruff check .` and `uv run pytest -v`) and verify zero lint errors and 100% green test execution.

# Sprint 2: PDF Ingestion Engine, LangGraph Self-Correcting Parser & Bronze Storage

- [x] Task 1: Update `pyproject.toml` dependencies via `uv add` for `reportlab`, `pypdf`, `langgraph`, `langchain-core`, and `langchain-openai`.
- [x] Task 2: Implement invoice schema contracts in `src/ingestion/models/invoice.py` using Pydantic v2 (`InvoiceItem`, `InvoiceMetadata`, `RawInvoicePayload`) with field-level validators for Brazilian CNPJ format, positive monetary values, and strict mathematical consistency (`total_amount == sum(items)`).
- [x] Task 3: Author synthetic PDF generator at `src/ingestion/generators/invoice_generator.py` using ReportLab, generating at least 3 distinct visual ERP invoice layouts for regional distributors containing Aura SKUs (`AURA_250ML`, `AURA_ZERO_250ML`, `AURA_TROPICAL_473ML`), batch numbers, and timestamps.
- [x] Task 4: Create text extraction utility at `src/ingestion/parsers/pdf_reader.py` leveraging `pypdf` to extract raw text and layout-preserving token streams from PDF files with error boundaries for corrupted files.
- [x] Task 5: Implement LangGraph state and node definitions at `src/ingestion/agents/invoice_graph.py`:
  - `InvoiceParserState`: tracks raw text, retry count, validation errors, and parsed Pydantic payload.
  - Extraction Node: executes LLM structured extraction with temperature 0.0.
  - Validation Node: checks Pydantic validation and financial invariant formulas.
  - Correction/Retry Router: loops back to correction prompt if errors exist (max 3 retries) or transitions to end.
- [x] Task 6: Implement ingestion repository at `src/ingestion/repositories/bronze_invoice_repo.py` to insert parsed payloads into `AURA_LAKEHOUSE.BRONZE.INVOICES_RAW` using parameterized SQL with Snowflake `PARSE_JSON(?)` inside the context-managed `SnowflakeClient`.
- [x] Task 7: Build pipeline entrypoint CLI at `src/ingestion/pipelines/run_invoice_ingestion.py` that generates batch sample PDFs, processes them through the LangGraph engine, and writes records into the Snowflake Bronze table with execution logging.
- [x] Task 8: Author unit tests in `tests/test_invoice_generator.py` asserting valid PDF binary generation and layout variations.
- [x] Task 9: Author unit tests in `tests/test_invoice_models.py` verifying Pydantic v2 validations, rejected negative values, invalid totals, and CNPJ formatting.
- [x] Task 10: Author unit tests in `tests/test_invoice_graph.py` mocking the LLM provider to test the cyclic self-correction loop, recovery on simulated parse failure, and successful termination.
- [x] Task 11: Author unit tests in `tests/test_bronze_invoice_repo.py` mocking `SnowflakeClient` to verify idempotent inserts, correct JSON parameter binding, and metadata attribution (`source_file`, `partner_id`).
- [x] Task 12: Run quality verification suite (`uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest -v`) confirming zero regressions and 100% green tests.

# Sprint 3: Multimodal Ingestion (Competitor Scraper, Open-Meteo Client, Legacy Inventory & Bronze Dagster SDAs)

- [x] Task 1: Update dependencies in `pyproject.toml` via `uv add` for `httpx`, `beautifulsoup4`, and `tenacity`.
- [x] Task 2: Update `scripts/init_snowflake.sql` and run `scripts/bootstrap_snowflake.py` to provision tables `BRONZE.COMPETITOR_PRICES_RAW`, `BRONZE.WEATHER_METRICS_RAW`, and `BRONZE.PARTNER_INVENTORY_RAW`.
- [x] Task 3: Implement dynamic logistics hubs registry in `src/ingestion/config/hubs.py` defining coordinates and metadata for multi-region distribution centers (SP, RJ, BH, Curitiba, Porto Alegre, Salvador, Recife, Fortaleza, Goiânia, Cuiabá).
- [x] Task 4: Implement domain contracts in `src/ingestion/models/multimodal.py` with Pydantic v2:
  - `CompetitorPriceRecord`: competitor brand (`RED_BULL`, `MONSTER`), product title, volume ml, price in BRL, stock status, timestamp.
  - `WeatherMetricRecord`: city hub, state, date, temp_max, temp_min, precipitation_sum.
  - `PartnerInventoryRecord`: partner_id, sku, batch_id, stock_quantity, warehouse_location, snapshot_date.
- [x] Task 5: Implement resilient Open-Meteo REST API client in `src/ingestion/clients/weather_client.py` using `httpx` with `tenacity` retry, iterating dynamically through all configured distribution hubs.
- [x] Task 6: Implement competitor price scraper at `src/ingestion/scrapers/competitor_scraper.py` using async `httpx` and `BeautifulSoup` to extract Red Bull and Monster prices, packaging structured records with resilience against connection drops and parsing errors.
- [x] Task 7: Implement legacy tabular inventory ingestor at `src/ingestion/parsers/tabular_inventory.py` supporting auto-detection of delimiters (`;`, `,`, `|`), encoding fallback (`utf-8`, `latin1`), MD5 file hashing, and normalization into Pydantic models.
- [x] Task 8: Implement Bronze repositories:
  - `BronzeCompetitorPriceRepository` in `src/ingestion/repositories/bronze_competitor_repo.py` targeting `BRONZE.COMPETITOR_PRICES_RAW`.
  - `BronzeWeatherRepository` in `src/ingestion/repositories/bronze_weather_repo.py` targeting `BRONZE.WEATHER_METRICS_RAW`.
  - `BronzePartnerInventoryRepository` in `src/ingestion/repositories/bronze_inventory_repo.py` targeting `BRONZE.PARTNER_INVENTORY_RAW`.
- [x] Task 9: Implement Dagster Software-Defined Assets (SDAs) in `src/orchestration/assets/bronze.py`:
  - Declare `@asset` definitions for `bronze_invoices_raw`, `bronze_weather_metrics_raw`, `bronze_competitor_prices_raw`, and `bronze_partner_inventory_raw` exposing asset keys, descriptions, and lineage metadata.
  - Register asset definitions in `src/orchestration/definitions.py`.
- [x] Task 10: Build lightweight ad-hoc CLI runner at `src/ingestion/pipelines/run_multimodal_ingestion.py` for local debugging and manual backfills with `--source` and `--dry-run` switches.
- [x] Task 11: Author unit tests in `tests/test_weather_client.py` mocking `httpx` responses across multiple distribution hubs and asserting retry behavior on HTTP 5xx.
- [x] Task 12: Author unit tests in `tests/test_competitor_scraper.py` mocking HTML responses to test price parsing, currency parsing, and stock detection.
- [x] Task 13: Author unit tests in `tests/test_tabular_inventory.py` validating CSV, semicolon, and pipe-delimited files, invalid rows rejection, and MD5 file hash calculations.
- [x] Task 14: Author unit tests in `tests/test_bronze_multimodal_repos.py` verifying parameterized inserts and `PARSE_JSON` bindings across the three new Bronze repositories with a mocked `SnowflakeClient`.
- [x] Task 15: Author unit tests in `tests/test_bronze_assets.py` validating Dagster asset materialization and context mocking.
- [x] Task 16: Execute full repository validation gates (`uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest -v`), ensuring 100% green tests with zero regressions.

# Sprint 4: Silver Layer Normalization, Deduplication & Push-Down SQL Transformations

- [x] Task 1: Update `scripts/init_snowflake.sql` with DDL for Silver tables (`INVOICES`, `INVOICE_ITEMS`, `COMPETITOR_PRICES`, `WEATHER_METRICS`, `PARTNER_INVENTORY`) and run `scripts/bootstrap_snowflake.py` to apply changes.
- [x] Task 2: Implement SQL transform query builder in `src/transformation/sql/silver_transforms.py` generating deterministic, idempotent `MERGE` statements with `QUALIFY ROW_NUMBER()` deduplication for all 5 Silver datasets.
- [x] Task 3: Implement Silver transformation service at `src/transformation/services/silver_service.py` with methods to execute transformations via `SnowflakeClient`:
  - `transform_invoices()`: Flattens and normalizes Bronze JSON into `SILVER.INVOICES` and `SILVER.INVOICE_ITEMS`.
  - `transform_competitor_prices()`: Cleans and deduplicates prices into `SILVER.COMPETITOR_PRICES`.
  - `transform_weather_metrics()`: Types and deduplicates metrics into `SILVER.WEATHER_METRICS`.
  - `transform_partner_inventory()`: Normalizes legacy inventory into `SILVER.PARTNER_INVENTORY`.
- [x] Task 4: Implement Dagster Silver Software-Defined Assets (SDAs) in `src/orchestration/assets/silver.py`:
  - Define `@asset` for `silver_invoices` and `silver_invoice_items` taking `bronze_invoices_raw` as input.
  - Define `@asset` for `silver_competitor_prices` taking `bronze_competitor_prices_raw` as input.
  - Define `@asset` for `silver_weather_metrics` taking `bronze_weather_metrics_raw` as input.
  - Define `@asset` for `silver_partner_inventory` taking `bronze_partner_inventory_raw` as input.
- [x] Task 5: Register Silver assets and graph dependencies in `src/orchestration/definitions.py`.
- [x] Task 6: Build CLI transformation entrypoint at `src/transformation/pipelines/run_silver_transforms.py` supporting `--target` (`all`, `invoices`, `competitors`, `weather`, `inventory`) and `--dry-run` modes.
- [x] Task 7: Author unit tests in `tests/test_silver_transforms_sql.py` verifying SQL syntax generation, parameter sanitization, and `QUALIFY` logic without connecting to live database.
- [x] Task 8: Author unit tests in `tests/test_silver_service.py` mocking `SnowflakeClient` to verify query execution order, transaction rollback on failure, and row count reporting.
- [x] Task 9: Author unit tests in `tests/test_silver_assets.py` validating Dagster asset dependency graph and materialization logic via `build_asset_context`.
- [x] Task 10: Author unit tests in `tests/test_run_silver_transforms.py` validating CLI argument parsing and error logging.
- [x] Task 11: Execute quality verification suite (`uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest -v`), ensuring all existing and new tests pass green.

# Sprint 5: Gold Layer Dimensional Modeling (Kimball Star Schema) & Analytical Marts

- [x] Task 1: Update `scripts/init_snowflake.sql` with DDL for Gold dimensions (`DIM_DATE`, `DIM_PARTNERS`, `DIM_SKUS`, `DIM_HUBS`), facts (`FACT_SELLOUT`, `FACT_INVENTORY_SNAPSHOT`, `FACT_COMPETITOR_PRICING`), and the analytical view `V_MARKET_INTELLIGENCE_AUDIT`, then execute `scripts/bootstrap_snowflake.py`.
- [x] Task 2: Implement SQL dimensional transform query builders in `src/transformation/sql/gold_transforms.py`:
  - `build_dim_date_sql()`: Deterministic date dimension generator using calendar sequences.
  - `build_dim_partners_sql()`: Extracts distinct partners from `SILVER.INVOICES` and `SILVER.PARTNER_INVENTORY` with `MD5(partner_id)` surrogate key.
  - `build_dim_skus_sql()`: Maps SKUs (`AURA_250ML`, `AURA_ZERO_250ML`, `AURA_TROPICAL_473ML`) with volume and flavor attributes.
  - `build_dim_hubs_sql()`: Populates distribution hubs with coordinates and surrogate keys.
  - `build_fact_sellout_sql()`: Denormalizes `SILVER.INVOICES` and `SILVER.INVOICE_ITEMS`, joins with dimensions to resolve foreign surrogate keys.
  - `build_fact_inventory_snapshot_sql()`: Resolves partner, sku, and date keys from `SILVER.PARTNER_INVENTORY`.
  - `build_fact_competitor_pricing_sql()`: Computes `price_per_ml` and normalizes stock status flags.
- [x] Task 3: Implement Gold transformation service in `src/transformation/services/gold_service.py` with methods to execute dimensional merges in proper dependency order (Dimensions first, then Facts) using `SnowflakeClient`.
- [x] Task 4: Implement Dagster Gold Software-Defined Assets (SDAs) in `src/orchestration/assets/gold.py`:
  - Declare `@asset` for dimensions: `gold_dim_date`, `gold_dim_partners`, `gold_dim_skus`, `gold_dim_hubs`.
  - Declare `@asset` for facts with dependencies on Silver tables and Gold dimensions: `gold_fact_sellout`, `gold_fact_inventory_snapshot`, `gold_fact_competitor_pricing`.
  - Register assets in `src/orchestration/definitions.py`.
- [x] Task 5: Extend CLI pipeline runner at `src/transformation/pipelines/run_gold_transforms.py` supporting `--target` (`dimensions`, `facts`, `all`) and `--dry-run`.
- [x] Task 6: Author unit tests in `tests/test_gold_transforms_sql.py` verifying SQL generation, surrogate key hash formulas, date math, and join clauses.
- [x] Task 7: Author unit tests in `tests/test_gold_service.py` mocking `SnowflakeClient` to verify dimensional load sequence and error handling.
- [x] Task 8: Author unit tests in `tests/test_gold_assets.py` verifying Dagster asset dependencies, upstream lineage, and schema metadata.
- [x] Task 9: Author unit tests in `tests/test_run_gold_transforms.py` validating CLI arguments and execution logs.
- [x] Task 10: Run full repository quality verification (`uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest -v`) ensuring zero regressions and all tests pass green.