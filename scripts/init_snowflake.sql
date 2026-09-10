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

-- Gold Dimension Table: Calendar Date Dimension
CREATE TABLE IF NOT EXISTS AURA_LAKEHOUSE.GOLD.DIM_DATE (
    date_key NUMBER(8, 0) NOT NULL,
    calendar_date DATE NOT NULL,
    year NUMBER(4, 0) NOT NULL,
    quarter NUMBER(1, 0) NOT NULL,
    month NUMBER(2, 0) NOT NULL,
    month_name VARCHAR(20) NOT NULL,
    day_of_month NUMBER(2, 0) NOT NULL,
    day_of_week NUMBER(1, 0) NOT NULL,
    day_name VARCHAR(20) NOT NULL,
    is_weekend BOOLEAN NOT NULL,
    is_holiday BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (date_key)
)
COMMENT = 'Gold calendar date dimension with day/month/quarter/weekend attributes';

-- Gold Dimension Table: Commercial Partners / Distributors
CREATE TABLE IF NOT EXISTS AURA_LAKEHOUSE.GOLD.DIM_PARTNERS (
    partner_key VARCHAR(32) NOT NULL,
    partner_id VARCHAR(100) NOT NULL,
    partner_cnpj VARCHAR(20),
    partner_name VARCHAR(255),
    channel_type VARCHAR(50) DEFAULT 'DISTRIBUTOR',
    first_seen_date DATE,
    last_active_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    transformed_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (partner_key)
)
COMMENT = 'Gold conformed dimension for distributors and partner accounts';

-- Gold Dimension Table: Product SKUs
CREATE TABLE IF NOT EXISTS AURA_LAKEHOUSE.GOLD.DIM_SKUS (
    sku_key VARCHAR(32) NOT NULL,
    sku VARCHAR(100) NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    flavor VARCHAR(100) NOT NULL,
    volume_ml NUMBER(10, 0) NOT NULL,
    package_type VARCHAR(50) NOT NULL,
    category VARCHAR(50) DEFAULT 'ENERGY_DRINK',
    transformed_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (sku_key)
)
COMMENT = 'Gold dimension mapping product SKUs, volume, flavor, and package specs';

-- Gold Dimension Table: Logistics Distribution Hubs
CREATE TABLE IF NOT EXISTS AURA_LAKEHOUSE.GOLD.DIM_HUBS (
    hub_key VARCHAR(32) NOT NULL,
    hub_id VARCHAR(100) NOT NULL,
    hub_name VARCHAR(255) NOT NULL,
    city VARCHAR(100) NOT NULL,
    state VARCHAR(10) NOT NULL,
    latitude NUMBER(10, 6) NOT NULL,
    longitude NUMBER(10, 6) NOT NULL,
    timezone VARCHAR(50) NOT NULL,
    transformed_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (hub_key)
)
COMMENT = 'Gold dimension for regional logistics hubs and distribution centers';

-- Gold Fact Table: B2B Partner Sell-Out Transactions
CREATE TABLE IF NOT EXISTS AURA_LAKEHOUSE.GOLD.FACT_SELLOUT (
    sellout_key VARCHAR(32) NOT NULL,
    date_key NUMBER(8, 0) NOT NULL,
    partner_key VARCHAR(32) NOT NULL,
    sku_key VARCHAR(32) NOT NULL,
    invoice_number VARCHAR(100) NOT NULL,
    batch_number VARCHAR(100) NOT NULL,
    quantity_sold NUMBER(10, 0) NOT NULL,
    unit_price NUMBER(12, 2) NOT NULL,
    total_price NUMBER(12, 2) NOT NULL,
    tax_amount NUMBER(12, 2) NOT NULL,
    net_revenue NUMBER(12, 2) NOT NULL,
    transformed_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (sellout_key)
)
COMMENT = 'Gold transactional fact recording B2B invoice sell-out volumes, revenues, and taxes';

-- Gold Fact Table: Partner Warehouse Daily Inventory Snapshots
CREATE TABLE IF NOT EXISTS AURA_LAKEHOUSE.GOLD.FACT_INVENTORY_SNAPSHOT (
    snapshot_key VARCHAR(32) NOT NULL,
    date_key NUMBER(8, 0) NOT NULL,
    partner_key VARCHAR(32) NOT NULL,
    sku_key VARCHAR(32) NOT NULL,
    batch_id VARCHAR(100) NOT NULL,
    warehouse_location VARCHAR(100) NOT NULL,
    stock_quantity NUMBER(10, 0) NOT NULL,
    snapshot_date DATE NOT NULL,
    transformed_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (snapshot_key)
)
COMMENT = 'Gold periodic snapshot fact tracking partner warehouse stock levels';

-- Gold Fact Table: Competitor Pricing & Market Intelligence
CREATE TABLE IF NOT EXISTS AURA_LAKEHOUSE.GOLD.FACT_COMPETITOR_PRICING (
    pricing_key VARCHAR(32) NOT NULL,
    date_key NUMBER(8, 0) NOT NULL,
    competitor_brand VARCHAR(50) NOT NULL,
    product_title VARCHAR(255) NOT NULL,
    volume_ml NUMBER(10, 0) NOT NULL,
    price_brl NUMBER(10, 2) NOT NULL,
    price_per_ml NUMBER(10, 4) NOT NULL,
    stock_status VARCHAR(20) NOT NULL,
    is_in_stock BOOLEAN NOT NULL,
    observed_at TIMESTAMP_NTZ NOT NULL,
    source_url VARCHAR(500) NOT NULL,
    transformed_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (pricing_key)
)
COMMENT = 'Gold fact tracking competitor retail price points and availability metrics';

-- Gold Analytical View: Market Intelligence & Sell-Out Audit
CREATE OR REPLACE VIEW AURA_LAKEHOUSE.GOLD.V_MARKET_INTELLIGENCE_AUDIT AS
SELECT
    d.calendar_date,
    d.year,
    d.quarter,
    d.month,
    d.month_name,
    p.partner_id,
    p.partner_name,
    p.channel_type,
    s.sku,
    s.product_name,
    s.flavor,
    s.volume_ml AS aura_volume_ml,
    fso.invoice_number,
    fso.batch_number,
    fso.quantity_sold,
    fso.unit_price,
    fso.total_price,
    fso.tax_amount,
    fso.net_revenue,
    ROUND(fso.unit_price / NULLIF(s.volume_ml, 0), 4) AS aura_price_per_ml,
    inv.stock_quantity AS partner_inventory_stock,
    w.city_hub AS climatic_hub,
    w.temp_max AS regional_temp_max,
    w.temp_min AS regional_temp_min,
    w.precipitation_sum AS regional_precipitation_sum
FROM AURA_LAKEHOUSE.GOLD.FACT_SELLOUT fso
JOIN AURA_LAKEHOUSE.GOLD.DIM_DATE d ON fso.date_key = d.date_key
JOIN AURA_LAKEHOUSE.GOLD.DIM_PARTNERS p ON fso.partner_key = p.partner_key
JOIN AURA_LAKEHOUSE.GOLD.DIM_SKUS s ON fso.sku_key = s.sku_key
LEFT JOIN AURA_LAKEHOUSE.GOLD.FACT_INVENTORY_SNAPSHOT inv
    ON fso.date_key = inv.date_key
    AND fso.partner_key = inv.partner_key
    AND fso.sku_key = inv.sku_key
    AND fso.batch_number = inv.batch_id
LEFT JOIN AURA_LAKEHOUSE.SILVER.WEATHER_METRICS w
    ON d.calendar_date = w.metric_date;



