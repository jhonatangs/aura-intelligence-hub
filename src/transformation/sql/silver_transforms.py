"""SQL transform query builders for the Snowflake Silver layer.

Generates deterministic, idempotent MERGE statements with QUALIFY ROW_NUMBER()
deduplication pushdown for all Silver tables.
"""

import re

VALID_DB_IDENTIFIER = re.compile(r"^[A-Za-z0-9_]+$")


def _sanitize_db(database: str) -> str:
    """Validate and sanitize Snowflake database identifier.

    Args:
        database: Database name to validate.

    Returns:
        str: Sanitized uppercase database name.

    Raises:
        ValueError: If database name contains invalid characters.
    """
    clean_db = database.strip().upper()
    if not VALID_DB_IDENTIFIER.match(clean_db):
        raise ValueError(f"Invalid database identifier: '{database}'")
    return clean_db


def build_merge_invoices_sql(database: str = "AURA_LAKEHOUSE") -> str:
    """Generate idempotent MERGE statement for SILVER.INVOICES.

    Deduplicates raw invoice JSON records by invoice_number and partner_id,
    keeping the latest ingested record.

    Args:
        database: Target Snowflake database name.

    Returns:
        str: Formatted MERGE SQL query.
    """
    db = _sanitize_db(database)
    return f"""MERGE INTO {db}.SILVER.INVOICES AS target
USING (
    SELECT
        payload:metadata:invoice_number::VARCHAR AS invoice_number,
        payload:metadata:partner_id::VARCHAR AS partner_id,
        payload:metadata:partner_cnpj::VARCHAR AS partner_cnpj,
        payload:metadata:issue_date::DATE AS issue_date,
        payload:subtotal::NUMBER(12, 2) AS subtotal,
        payload:tax_amount::NUMBER(12, 2) AS tax_amount,
        payload:total_amount::NUMBER(12, 2) AS total_amount,
        source_file,
        ingested_at
    FROM {db}.BRONZE.INVOICES_RAW
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY payload:metadata:invoice_number::VARCHAR, payload:metadata:partner_id::VARCHAR
        ORDER BY ingested_at DESC
    ) = 1
) AS src
ON target.invoice_number = src.invoice_number AND target.partner_id = src.partner_id
WHEN MATCHED THEN
    UPDATE SET
        target.partner_cnpj = src.partner_cnpj,
        target.issue_date = src.issue_date,
        target.subtotal = src.subtotal,
        target.tax_amount = src.tax_amount,
        target.total_amount = src.total_amount,
        target.source_file = src.source_file,
        target.ingested_at = src.ingested_at,
        target.transformed_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
    INSERT (
        invoice_number,
        partner_id,
        partner_cnpj,
        issue_date,
        subtotal,
        tax_amount,
        total_amount,
        source_file,
        ingested_at,
        transformed_at
    )
    VALUES (
        src.invoice_number,
        src.partner_id,
        src.partner_cnpj,
        src.issue_date,
        src.subtotal,
        src.tax_amount,
        src.total_amount,
        src.source_file,
        src.ingested_at,
        CURRENT_TIMESTAMP()
    )"""


def build_merge_invoice_items_sql(database: str = "AURA_LAKEHOUSE") -> str:
    """Generate idempotent MERGE statement for SILVER.INVOICE_ITEMS.

    Flattens invoice line items from raw JSON array and deduplicates by
    invoice_number, partner_id, sku, and batch_number.

    Args:
        database: Target Snowflake database name.

    Returns:
        str: Formatted MERGE SQL query.
    """
    db = _sanitize_db(database)
    return f"""MERGE INTO {db}.SILVER.INVOICE_ITEMS AS target
USING (
    SELECT
        payload:metadata:invoice_number::VARCHAR AS invoice_number,
        payload:metadata:partner_id::VARCHAR AS partner_id,
        item.value:sku::VARCHAR AS sku,
        item.value:description::VARCHAR AS description,
        item.value:quantity::NUMBER(10, 0) AS quantity,
        item.value:unit_price::NUMBER(12, 2) AS unit_price,
        item.value:total_price::NUMBER(12, 2) AS total_price,
        item.value:batch_number::VARCHAR AS batch_number,
        source_file,
        ingested_at
    FROM {db}.BRONZE.INVOICES_RAW,
    LATERAL FLATTEN(INPUT => payload:items) AS item
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY
            payload:metadata:invoice_number::VARCHAR,
            payload:metadata:partner_id::VARCHAR,
            item.value:sku::VARCHAR,
            item.value:batch_number::VARCHAR
        ORDER BY ingested_at DESC
    ) = 1
) AS src
ON target.invoice_number = src.invoice_number
    AND target.partner_id = src.partner_id
    AND target.sku = src.sku
    AND target.batch_number = src.batch_number
WHEN MATCHED THEN
    UPDATE SET
        target.description = src.description,
        target.quantity = src.quantity,
        target.unit_price = src.unit_price,
        target.total_price = src.total_price,
        target.source_file = src.source_file,
        target.transformed_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
    INSERT (
        invoice_number,
        partner_id,
        sku,
        description,
        quantity,
        unit_price,
        total_price,
        batch_number,
        source_file,
        transformed_at
    )
    VALUES (
        src.invoice_number,
        src.partner_id,
        src.sku,
        src.description,
        src.quantity,
        src.unit_price,
        src.total_price,
        src.batch_number,
        src.source_file,
        CURRENT_TIMESTAMP()
    )"""


def build_merge_competitor_prices_sql(database: str = "AURA_LAKEHOUSE") -> str:
    """Generate idempotent MERGE statement for SILVER.COMPETITOR_PRICES.

    Deduplicates scraped competitor prices by competitor_brand, product_title,
    and observed_at timestamp.

    Args:
        database: Target Snowflake database name.

    Returns:
        str: Formatted MERGE SQL query.
    """
    db = _sanitize_db(database)
    return f"""MERGE INTO {db}.SILVER.COMPETITOR_PRICES AS target
USING (
    SELECT
        competitor_brand,
        payload:product_title::VARCHAR AS product_title,
        payload:volume_ml::NUMBER(10, 0) AS volume_ml,
        payload:price_brl::NUMBER(10, 2) AS price_brl,
        payload:stock_status::VARCHAR AS stock_status,
        payload:timestamp::TIMESTAMP_NTZ AS observed_at,
        source_url,
        ingested_at
    FROM {db}.BRONZE.COMPETITOR_PRICES_RAW
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY
            competitor_brand,
            payload:product_title::VARCHAR,
            payload:timestamp::TIMESTAMP_NTZ
        ORDER BY ingested_at DESC
    ) = 1
) AS src
ON target.competitor_brand = src.competitor_brand
    AND target.product_title = src.product_title
    AND target.observed_at = src.observed_at
WHEN MATCHED THEN
    UPDATE SET
        target.volume_ml = src.volume_ml,
        target.price_brl = src.price_brl,
        target.stock_status = src.stock_status,
        target.source_url = src.source_url,
        target.transformed_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
    INSERT (
        competitor_brand,
        product_title,
        volume_ml,
        price_brl,
        stock_status,
        observed_at,
        source_url,
        transformed_at
    )
    VALUES (
        src.competitor_brand,
        src.product_title,
        src.volume_ml,
        src.price_brl,
        src.stock_status,
        src.observed_at,
        src.source_url,
        CURRENT_TIMESTAMP()
    )"""


def build_merge_weather_metrics_sql(database: str = "AURA_LAKEHOUSE") -> str:
    """Generate idempotent MERGE statement for SILVER.WEATHER_METRICS.

    Deduplicates macro climatic metric observations by city_hub and metric_date.

    Args:
        database: Target Snowflake database name.

    Returns:
        str: Formatted MERGE SQL query.
    """
    db = _sanitize_db(database)
    return f"""MERGE INTO {db}.SILVER.WEATHER_METRICS AS target
USING (
    SELECT
        city_hub,
        state,
        payload:date::DATE AS metric_date,
        payload:temp_max::NUMBER(5, 2) AS temp_max,
        payload:temp_min::NUMBER(5, 2) AS temp_min,
        payload:precipitation_sum::NUMBER(7, 2) AS precipitation_sum,
        ingested_at
    FROM {db}.BRONZE.WEATHER_METRICS_RAW
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY city_hub, payload:date::DATE
        ORDER BY ingested_at DESC
    ) = 1
) AS src
ON target.city_hub = src.city_hub
    AND target.metric_date = src.metric_date
WHEN MATCHED THEN
    UPDATE SET
        target.state = src.state,
        target.temp_max = src.temp_max,
        target.temp_min = src.temp_min,
        target.precipitation_sum = src.precipitation_sum,
        target.transformed_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
    INSERT (
        city_hub,
        state,
        metric_date,
        temp_max,
        temp_min,
        precipitation_sum,
        transformed_at
    )
    VALUES (
        src.city_hub,
        src.state,
        src.metric_date,
        src.temp_max,
        src.temp_min,
        src.precipitation_sum,
        CURRENT_TIMESTAMP()
    )"""


def build_merge_partner_inventory_sql(database: str = "AURA_LAKEHOUSE") -> str:
    """Generate idempotent MERGE statement for SILVER.PARTNER_INVENTORY.

    Deduplicates legacy inventory balances by partner_id, sku, batch_id,
    warehouse_location, and snapshot_date.

    Args:
        database: Target Snowflake database name.

    Returns:
        str: Formatted MERGE SQL query.
    """
    db = _sanitize_db(database)
    return f"""MERGE INTO {db}.SILVER.PARTNER_INVENTORY AS target
USING (
    SELECT
        partner_id,
        payload:sku::VARCHAR AS sku,
        payload:batch_id::VARCHAR AS batch_id,
        payload:stock_quantity::NUMBER(10, 0) AS stock_quantity,
        payload:warehouse_location::VARCHAR AS warehouse_location,
        payload:snapshot_date::DATE AS snapshot_date,
        file_hash_md5,
        source_file,
        ingested_at
    FROM {db}.BRONZE.PARTNER_INVENTORY_RAW
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY
            partner_id,
            payload:sku::VARCHAR,
            payload:batch_id::VARCHAR,
            payload:warehouse_location::VARCHAR,
            payload:snapshot_date::DATE
        ORDER BY ingested_at DESC
    ) = 1
) AS src
ON target.partner_id = src.partner_id
    AND target.sku = src.sku
    AND target.batch_id = src.batch_id
    AND target.warehouse_location = src.warehouse_location
    AND target.snapshot_date = src.snapshot_date
WHEN MATCHED THEN
    UPDATE SET
        target.stock_quantity = src.stock_quantity,
        target.file_hash_md5 = src.file_hash_md5,
        target.source_file = src.source_file,
        target.transformed_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
    INSERT (
        partner_id,
        sku,
        batch_id,
        stock_quantity,
        warehouse_location,
        snapshot_date,
        file_hash_md5,
        source_file,
        transformed_at
    )
    VALUES (
        src.partner_id,
        src.sku,
        src.batch_id,
        src.stock_quantity,
        src.warehouse_location,
        src.snapshot_date,
        src.file_hash_md5,
        src.source_file,
        CURRENT_TIMESTAMP()
    )"""


def get_all_silver_merge_queries(database: str = "AURA_LAKEHOUSE") -> dict[str, str]:
    """Retrieve all Silver layer MERGE query definitions.

    Args:
        database: Target Snowflake database name.

    Returns:
        dict[str, str]: Mapping of dataset key to SQL query string.
    """
    return {
        "invoices": build_merge_invoices_sql(database),
        "invoice_items": build_merge_invoice_items_sql(database),
        "competitor_prices": build_merge_competitor_prices_sql(database),
        "weather_metrics": build_merge_weather_metrics_sql(database),
        "partner_inventory": build_merge_partner_inventory_sql(database),
    }
