# 📋 Backlog & Tasks

Use this file to guide the autonomous agent. The agent must change the status from [ ] to [x] ONLY when the pipeline passes and the task is fully documented in the handoff state.

# Sprint 1: Bootstrap, Governance, RSA Key-Pair Config & Snowflake IaC

- [ ] Task 1: Initialize Git and update `.gitignore` ensuring strict exclusion of `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.ruff_cache/`, `.env`, `data/raw/`, `*.db`, and cryptographical artifacts (`*.p8`, `*.pem`, `*.pub`).
- [ ] Task 2: Create governance documentation under `.ai/rules/` (`01-global.md`, `02-python.md`, `03-data.md`, `04-ai-ops.md`, `05-frontend.md`) defining PEP 621 conventions, Ruff standards, deterministic type hints, and isolated mock-testing protocols.
- [ ] Task 3: Author comprehensive domain context file at `.ai/context.md` covering:
  - Domain & Business Scope: Aura Energy Drink competitive intelligence and supply chain audit against Red Bull and Monster Energy.
  - Ingestion Topologies:
    1. Partner B2B Invoices (Sell-Out): Synthetic PDFs via ReportLab -> LangGraph cyclic stateful parser with Pydantic v2 validation -> `AURA_LAKEHOUSE.BRONZE.INVOICES_RAW` (VARIANT payload).
    2. Competitor Pricing Intelligence: Concurrent scraper for Red Bull and Monster -> `BRONZE.COMPETITOR_PRICES_RAW`.
    3. Macro Climatic Context: Open-Meteo REST API (daily max temp & precipitation for SP, RJ, BH) -> `BRONZE.WEATHER_METRICS_RAW`.
    4. Legacy Partner Warehouse Inventories: Delimited tabular files (CSV/TXT with `;`, `,`, `|`) -> `BRONZE.PARTNER_INVENTORY_RAW`.
  - Architecture & Infrastructure: `uv` package manager with `pyproject.toml` (PEP 621), Snowflake Medallion Lakehouse with idempotent SQL IaC (`COMPUTE_WH` X-SMALL, suspended, auto-suspend 60s), and Dagster Software-Defined Assets (SDAs).
- [ ] Task 4: Provision repository folder layout creating `src/common`, `src/ingestion`, `src/transformation`, `src/orchestration`, `tests/`, `scripts/`, and `data/raw/partners/` with respective `__init__.py` module descriptors.
- [ ] Task 5: Configure `pyproject.toml` targeting Python 3.11+ with `[tool.ruff]` (lint rules: E, F, I, UP, B, line-length 100) and `[tool.pytest.ini_options]` (`pythonpath = ["src"]` and standard test discovery).
- [ ] Task 6: Create `.env.example` declaring required connection parameters using RSA key-pair authentication (`SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PRIVATE_KEY_PATH`, `SNOWFLAKE_PRIVATE_KEY_PASSPHRASE`, `SNOWFLAKE_ROLE`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`, `SNOWFLAKE_SCHEMA`), omitting any plain-text password variables.
- [ ] Task 7: Implement immutable configuration model in `src/common/config.py` using `pydantic_settings.BaseSettings`, validating environment parameters, path existence for the private key file, and exposing typed properties.
- [ ] Task 8: Author idempotent Snowflake SQL provisioning script at `scripts/init_snowflake.sql` defining warehouse `COMPUTE_WH` (size X-SMALL, auto-suspend 60, auto-resume true, initially suspended), database `AURA_LAKEHOUSE`, schemas `BRONZE`, `SILVER`, `GOLD`, and the raw ingestion table `BRONZE.INVOICES_RAW` with ingestion metadata (`source_file`, `partner_id`, `ingested_at`) and a `VARIANT` payload column.
- [ ] Task 9: Implement enterprise Snowflake connection client in `src/common/snowflake_client.py` using a Python Context Manager (`__enter__` and `__exit__`), using `cryptography` to deserialize the PKCS#8 private key and converting it to DER format for `snowflake.connector.connect`.
- [ ] Task 10: Author Python bootstrapping script at `scripts/bootstrap_snowflake.py` to parse and execute statements sequentially from `scripts/init_snowflake.sql` using the context-managed Snowflake client.
- [ ] Task 11: Author unit tests in `tests/test_config.py` using `monkeypatch` and `tmp_path` to validate successful configuration loading, proper error handling for missing files, and rejection of invalid private key paths.
- [ ] Task 12: Author unit tests in `tests/test_snowflake_client.py` mocking `cryptography.hazmat.primitives.serialization.load_pem_private_key` and `snowflake.connector.connect` to verify private key loading, DER serialization, connection parameters, cursor lifecycle, and deterministic cleanup on execution errors.
- [ ] Task 13: Run quality gate verification commands (`uv run ruff check .` and `uv run pytest -v`) and verify zero lint errors and 100% green test execution.
