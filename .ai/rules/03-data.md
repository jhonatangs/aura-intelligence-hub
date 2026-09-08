# 🗄️ Data Engineering & Snowflake Lakehouse Rules

- **Architectural Pattern**: Strictly adhere to the Snowflake Medallion Lakehouse pattern defined in `.ai/context.md`:
  - **Bronze Layer (`AURA_LAKEHOUSE.BRONZE`)**: Raw, immutable landing zone. Preserves source schema using semi-structured `VARIANT` columns alongside tracking metadata (`source_file`, `partner_id`, `ingested_at`).
  - **Silver Layer (`AURA_LAKEHOUSE.SILVER`)**: Conformed, deduplicated, and cleansed relational tables with explicit types and constraints.
  - **Gold Layer (`AURA_LAKEHOUSE.GOLD`)**: Business aggregation layer, star-schema dimensional models, and analytical views.
- **Snowflake IaC & DDL Standards**:
  - All database infrastructure must be codified into idempotent SQL provisioning scripts (`CREATE ... IF NOT EXISTS`).
  - Virtual warehouses must specify auto-suspend (60s), auto-resume (`TRUE`), and start in a suspended state (`INITIALLY_SUSPENDED = TRUE`) to prevent compute waste.
  - All SQL keywords must be UPPERCASE.
  - Favor Common Table Expressions (CTEs) over deeply nested subqueries for clarity and query optimizer efficiency.
- **Orchestration & Dagster SDAs**:
  - Orchestrate data flows via Dagster Software-Defined Assets (SDAs).
  - Pipeline assets must be strictly idempotent and deterministic upon re-execution.
  - Delegate heavy transformations to Snowflake SQL pushdown; keep orchestrator memory footprint lightweight.
- **Data Quality & Contracts**:
  - Ingestion pipelines must validate payloads against Pydantic schemas prior to loading.
  - Final consumption models (Silver/Gold) must enforce automated data quality assertions: primary key uniqueness, non-nullability, foreign key referential integrity, and expected value distributions.
