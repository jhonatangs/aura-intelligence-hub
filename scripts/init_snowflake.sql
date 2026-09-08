-- =============================================================================
-- Snowflake IaC Provisioning Script: Aura Intelligence Hub Lakehouse
-- Idempotent DDL for Warehouse, Database, Schemas, and Bronze Ingestion Tables
-- =============================================================================

-- Virtual Warehouse Configuration
CREATE WAREHOUSE IF NOT EXISTS COMPUTE_WH
    WITH WAREHOUSE_SIZE = 'X-SMALL'
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE
    COMMENT = 'Virtual warehouse for Aura Intelligence Hub data processing';

-- Lakehouse Database
CREATE DATABASE IF NOT EXISTS AURA_LAKEHOUSE
    COMMENT = 'Enterprise Lakehouse for Aura Energy Drink competitive intelligence';

-- Medallion Architecture Schemas
CREATE SCHEMA IF NOT EXISTS AURA_LAKEHOUSE.BRONZE
    COMMENT = 'Raw landing and immutable ingestion layer';

CREATE SCHEMA IF NOT EXISTS AURA_LAKEHOUSE.SILVER
    COMMENT = 'Conformed, cleansed, and enriched relational models';

CREATE SCHEMA IF NOT EXISTS AURA_LAKEHOUSE.GOLD
    COMMENT = 'Curated dimensional models, aggregated metrics, and analytical views';

-- Bronze Ingestion Table: Partner B2B Invoices
CREATE TABLE IF NOT EXISTS AURA_LAKEHOUSE.BRONZE.INVOICES_RAW (
    source_file VARCHAR(500) NOT NULL,
    partner_id VARCHAR(100) NOT NULL,
    ingested_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    payload VARIANT NOT NULL
)
COMMENT = 'Raw B2B partner invoice JSON payloads parsed via LangGraph with ingestion metadata';
