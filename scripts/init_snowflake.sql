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

-- Bronze Ingestion Table: Competitor Pricing Intelligence
CREATE TABLE IF NOT EXISTS AURA_LAKEHOUSE.BRONZE.COMPETITOR_PRICES_RAW (
    source_url VARCHAR(500) NOT NULL,
    competitor_brand VARCHAR(50) NOT NULL,
    ingested_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    payload VARIANT NOT NULL
)
COMMENT = 'Raw competitor pricing intelligence scraped from e-commerce and retail channels';

-- Bronze Ingestion Table: Macro Climatic Context
CREATE TABLE IF NOT EXISTS AURA_LAKEHOUSE.BRONZE.WEATHER_METRICS_RAW (
    city_hub VARCHAR(100) NOT NULL,
    state VARCHAR(10) NOT NULL,
    ingested_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    payload VARIANT NOT NULL
)
COMMENT = 'Raw Open-Meteo macro climatic metrics for regional distribution hubs';

-- Bronze Ingestion Table: Legacy Partner Warehouse Inventories
CREATE TABLE IF NOT EXISTS AURA_LAKEHOUSE.BRONZE.PARTNER_INVENTORY_RAW (
    source_file VARCHAR(500) NOT NULL,
    partner_id VARCHAR(100) NOT NULL,
    file_hash_md5 VARCHAR(32) NOT NULL,
    ingested_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    payload VARIANT NOT NULL
)
COMMENT = 'Raw partner warehouse inventory snapshots parsed from legacy delimited tabular extracts';

-- Silver Conformed Table: Partner B2B Invoices (Header Grain)
CREATE TABLE IF NOT EXISTS AURA_LAKEHOUSE.SILVER.INVOICES (
    invoice_number VARCHAR(100) NOT NULL,
    partner_id VARCHAR(100) NOT NULL,
    partner_cnpj VARCHAR(20) NOT NULL,
    issue_date DATE NOT NULL,
    subtotal NUMBER(12, 2) NOT NULL,
    tax_amount NUMBER(12, 2) NOT NULL,
    total_amount NUMBER(12, 2) NOT NULL,
    source_file VARCHAR(500) NOT NULL,
    ingested_at TIMESTAMP_NTZ NOT NULL,
    transformed_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (invoice_number, partner_id)
)
COMMENT = 'Cleansed and deduplicated partner B2B invoice header records';

-- Silver Conformed Table: Partner B2B Invoice Line Items
CREATE TABLE IF NOT EXISTS AURA_LAKEHOUSE.SILVER.INVOICE_ITEMS (
    invoice_number VARCHAR(100) NOT NULL,
    partner_id VARCHAR(100) NOT NULL,
    sku VARCHAR(100) NOT NULL,
    description VARCHAR(255) NOT NULL,
    quantity NUMBER(10, 0) NOT NULL,
    unit_price NUMBER(12, 2) NOT NULL,
    total_price NUMBER(12, 2) NOT NULL,
    batch_number VARCHAR(100) NOT NULL,
    source_file VARCHAR(500) NOT NULL,
    transformed_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (invoice_number, partner_id, sku, batch_number)
)
COMMENT = 'Normalized and flattened partner B2B invoice line items';

-- Silver Conformed Table: Competitor Pricing Intelligence
CREATE TABLE IF NOT EXISTS AURA_LAKEHOUSE.SILVER.COMPETITOR_PRICES (
    competitor_brand VARCHAR(50) NOT NULL,
    product_title VARCHAR(255) NOT NULL,
    volume_ml NUMBER(10, 0) NOT NULL,
    price_brl NUMBER(10, 2) NOT NULL,
    stock_status VARCHAR(20) NOT NULL,
    observed_at TIMESTAMP_NTZ NOT NULL,
    source_url VARCHAR(500) NOT NULL,
    transformed_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (competitor_brand, product_title, observed_at)
)
COMMENT = 'Cleansed and deduplicated competitor price observations for Red Bull and Monster';

-- Silver Conformed Table: Macro Climatic Observations
CREATE TABLE IF NOT EXISTS AURA_LAKEHOUSE.SILVER.WEATHER_METRICS (
    city_hub VARCHAR(100) NOT NULL,
    state VARCHAR(10) NOT NULL,
    metric_date DATE NOT NULL,
    temp_max NUMBER(5, 2) NOT NULL,
    temp_min NUMBER(5, 2) NOT NULL,
    precipitation_sum NUMBER(7, 2) NOT NULL,
    transformed_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (city_hub, metric_date)
)
COMMENT = 'Normalized daily temperature and precipitation observations per logistics distribution hub';

-- Silver Conformed Table: Legacy Partner Warehouse Inventories
CREATE TABLE IF NOT EXISTS AURA_LAKEHOUSE.SILVER.PARTNER_INVENTORY (
    partner_id VARCHAR(100) NOT NULL,
    sku VARCHAR(100) NOT NULL,
    batch_id VARCHAR(100) NOT NULL,
    stock_quantity NUMBER(10, 0) NOT NULL,
    warehouse_location VARCHAR(100) NOT NULL,
    snapshot_date DATE NOT NULL,
    file_hash_md5 VARCHAR(32) NOT NULL,
    source_file VARCHAR(500) NOT NULL,
    transformed_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (partner_id, sku, batch_id, warehouse_location, snapshot_date)
)
COMMENT = 'Cleansed and deduplicated partner inventory balances by warehouse location and snapshot date';


