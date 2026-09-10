"""SQL dimensional transform query builders for the Snowflake Gold layer.

Generates deterministic, idempotent MERGE statements for Kimball Star Schema
dimensions and facts in the Gold layer.
"""

import re

from src.ingestion.config.hubs import DISTRIBUTION_HUBS

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


def build_dim_date_sql(database: str = "AURA_LAKEHOUSE") -> str:
    """Generate idempotent MERGE statement for GOLD.DIM_DATE.

    Generates a deterministic 5-year calendar date spine (2023-2027) with
    day, month, quarter, year, and weekend flags.

    Args:
        database: Target Snowflake database name.

    Returns:
        str: Formatted MERGE SQL query.
    """
    db = _sanitize_db(database)
    return f"""MERGE INTO {db}.GOLD.DIM_DATE AS target
USING (
    WITH date_spine AS (
        SELECT DATEADD(DAY, SEQ4(), '2023-01-01'::DATE) AS calendar_date
        FROM TABLE(GENERATOR(ROWCOUNT => 1826))
    )
    SELECT
        TO_NUMBER(TO_VARCHAR(calendar_date, 'YYYYMMDD')) AS date_key,
        calendar_date,
        YEAR(calendar_date)::NUMBER(4, 0) AS year,
        QUARTER(calendar_date)::NUMBER(1, 0) AS quarter,
        MONTH(calendar_date)::NUMBER(2, 0) AS month,
        MONTHNAME(calendar_date)::VARCHAR(20) AS month_name,
        DAY(calendar_date)::NUMBER(2, 0) AS day_of_month,
        DAYOFWEEK(calendar_date)::NUMBER(1, 0) AS day_of_week,
        DAYNAME(calendar_date)::VARCHAR(20) AS day_name,
        CASE WHEN DAYOFWEEK(calendar_date) IN (0, 6) THEN TRUE ELSE FALSE END AS is_weekend,
        FALSE AS is_holiday
    FROM date_spine
) AS src
ON target.date_key = src.date_key
WHEN MATCHED THEN
    UPDATE SET
        target.calendar_date = src.calendar_date,
        target.year = src.year,
        target.quarter = src.quarter,
        target.month = src.month,
        target.month_name = src.month_name,
        target.day_of_month = src.day_of_month,
        target.day_of_week = src.day_of_week,
        target.day_name = src.day_name,
        target.is_weekend = src.is_weekend,
        target.is_holiday = src.is_holiday
WHEN NOT MATCHED THEN
    INSERT (
        date_key,
        calendar_date,
        year,
        quarter,
        month,
        month_name,
        day_of_month,
        day_of_week,
        day_name,
        is_weekend,
        is_holiday
    )
    VALUES (
        src.date_key,
        src.calendar_date,
        src.year,
        src.quarter,
        src.month,
        src.month_name,
        src.day_of_month,
        src.day_of_week,
        src.day_name,
        src.is_weekend,
        src.is_holiday
    )"""


def build_dim_partners_sql(database: str = "AURA_LAKEHOUSE") -> str:
    """Generate idempotent MERGE statement for GOLD.DIM_PARTNERS.

    Extracts distinct commercial partners from SILVER.INVOICES and
    SILVER.PARTNER_INVENTORY with MD5(partner_id) surrogate key.

    Args:
        database: Target Snowflake database name.

    Returns:
        str: Formatted MERGE SQL query.
    """
    db = _sanitize_db(database)
    return f"""MERGE INTO {db}.GOLD.DIM_PARTNERS AS target
USING (
    WITH raw_partners AS (
        SELECT
            partner_id,
            partner_cnpj,
            issue_date AS activity_date
        FROM {db}.SILVER.INVOICES
        UNION ALL
        SELECT
            partner_id,
            NULL AS partner_cnpj,
            snapshot_date AS activity_date
        FROM {db}.SILVER.PARTNER_INVENTORY
    ),
    aggregated_partners AS (
        SELECT
            partner_id,
            MAX(partner_cnpj) AS partner_cnpj,
            MIN(activity_date) AS first_seen_date,
            MAX(activity_date) AS last_active_date
        FROM raw_partners
        GROUP BY partner_id
    )
    SELECT
        MD5(partner_id) AS partner_key,
        partner_id,
        COALESCE(partner_cnpj, 'UNKNOWN') AS partner_cnpj,
        CONCAT('Partner ', partner_id) AS partner_name,
        'DISTRIBUTOR' AS channel_type,
        first_seen_date,
        last_active_date,
        TRUE AS is_active
    FROM aggregated_partners
) AS src
ON target.partner_key = src.partner_key
WHEN MATCHED THEN
    UPDATE SET
        target.partner_cnpj = src.partner_cnpj,
        target.partner_name = src.partner_name,
        target.channel_type = src.channel_type,
        target.first_seen_date = src.first_seen_date,
        target.last_active_date = src.last_active_date,
        target.is_active = src.is_active,
        target.transformed_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
    INSERT (
        partner_key,
        partner_id,
        partner_cnpj,
        partner_name,
        channel_type,
        first_seen_date,
        last_active_date,
        is_active,
        transformed_at
    )
    VALUES (
        src.partner_key,
        src.partner_id,
        src.partner_cnpj,
        src.partner_name,
        src.channel_type,
        src.first_seen_date,
        src.last_active_date,
        src.is_active,
        CURRENT_TIMESTAMP()
    )"""


def build_dim_skus_sql(database: str = "AURA_LAKEHOUSE") -> str:
    """Generate idempotent MERGE statement for GOLD.DIM_SKUS.

    Maps product SKUs (AURA_250ML, AURA_ZERO_250ML, AURA_TROPICAL_473ML)
    with volume, flavor, and packaging specifications.

    Args:
        database: Target Snowflake database name.

    Returns:
        str: Formatted MERGE SQL query.
    """
    db = _sanitize_db(database)
    return f"""MERGE INTO {db}.GOLD.DIM_SKUS AS target
USING (
    WITH distinct_skus AS (
        SELECT sku FROM {db}.SILVER.INVOICE_ITEMS
        UNION
        SELECT sku FROM {db}.SILVER.PARTNER_INVENTORY
        UNION
        SELECT 'AURA_250ML' AS sku
        UNION
        SELECT 'AURA_ZERO_250ML' AS sku
        UNION
        SELECT 'AURA_TROPICAL_473ML' AS sku
    )
    SELECT
        MD5(sku) AS sku_key,
        sku,
        CASE
            WHEN sku = 'AURA_250ML' THEN 'Aura Energy Original 250ml'
            WHEN sku = 'AURA_ZERO_250ML' THEN 'Aura Energy Sugar Free 250ml'
            WHEN sku = 'AURA_TROPICAL_473ML' THEN 'Aura Energy Tropical 473ml'
            ELSE CONCAT('Aura Product ', sku)
        END AS product_name,
        CASE
            WHEN sku = 'AURA_250ML' THEN 'Original'
            WHEN sku = 'AURA_ZERO_250ML' THEN 'Sugar Free'
            WHEN sku = 'AURA_TROPICAL_473ML' THEN 'Tropical'
            ELSE 'Standard'
        END AS flavor,
        CASE
            WHEN sku = 'AURA_250ML' THEN 250
            WHEN sku = 'AURA_ZERO_250ML' THEN 250
            WHEN sku = 'AURA_TROPICAL_473ML' THEN 473
            ELSE 250
        END AS volume_ml,
        'CAN' AS package_type,
        'ENERGY_DRINK' AS category
    FROM distinct_skus
) AS src
ON target.sku_key = src.sku_key
WHEN MATCHED THEN
    UPDATE SET
        target.product_name = src.product_name,
        target.flavor = src.flavor,
        target.volume_ml = src.volume_ml,
        target.package_type = src.package_type,
        target.category = src.category,
        target.transformed_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
    INSERT (
        sku_key,
        sku,
        product_name,
        flavor,
        volume_ml,
        package_type,
        category,
        transformed_at
    )
    VALUES (
        src.sku_key,
        src.sku,
        src.product_name,
        src.flavor,
        src.volume_ml,
        src.package_type,
        src.category,
        CURRENT_TIMESTAMP()
    )"""


def build_dim_hubs_sql(database: str = "AURA_LAKEHOUSE") -> str:
    """Generate idempotent MERGE statement for GOLD.DIM_HUBS.

    Populates distribution hubs with geographic coordinates and surrogate keys
    from the centralized DISTRIBUTION_HUBS registry.

    Args:
        database: Target Snowflake database name.

    Returns:
        str: Formatted MERGE SQL query.
    """
    db = _sanitize_db(database)
    values_rows = []
    for hub in DISTRIBUTION_HUBS:
        clean_name = hub.name.replace("'", "''")
        clean_city = hub.city.replace("'", "''")
        row_str = (
            f"('{hub.hub_id}', '{clean_name}', '{clean_city}', "
            f"'{hub.state}', {hub.latitude:.6f}, {hub.longitude:.6f}, '{hub.timezone}')"
        )
        values_rows.append(row_str)

    values_clause = ",\n        ".join(values_rows)

    return f"""MERGE INTO {db}.GOLD.DIM_HUBS AS target
USING (
    SELECT
        MD5(column1) AS hub_key,
        column1::VARCHAR AS hub_id,
        column2::VARCHAR AS hub_name,
        column3::VARCHAR AS city,
        column4::VARCHAR AS state,
        column5::NUMBER(10, 6) AS latitude,
        column6::NUMBER(10, 6) AS longitude,
        column7::VARCHAR AS timezone
    FROM (VALUES
        {values_clause}
    )
) AS src
ON target.hub_key = src.hub_key
WHEN MATCHED THEN
    UPDATE SET
        target.hub_name = src.hub_name,
        target.city = src.city,
        target.state = src.state,
        target.latitude = src.latitude,
        target.longitude = src.longitude,
        target.timezone = src.timezone,
        target.transformed_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
    INSERT (
        hub_key,
        hub_id,
        hub_name,
        city,
        state,
        latitude,
        longitude,
        timezone,
        transformed_at
    )
    VALUES (
        src.hub_key,
        src.hub_id,
        src.hub_name,
        src.city,
        src.state,
        src.latitude,
        src.longitude,
        src.timezone,
        CURRENT_TIMESTAMP()
    )"""


def build_fact_sellout_sql(database: str = "AURA_LAKEHOUSE") -> str:
    """Generate idempotent MERGE statement for GOLD.FACT_SELLOUT.

    Denormalizes SILVER.INVOICES and SILVER.INVOICE_ITEMS and resolves
    surrogate foreign keys for date, partner, and SKU dimensions.

    Args:
        database: Target Snowflake database name.

    Returns:
        str: Formatted MERGE SQL query.
    """
    db = _sanitize_db(database)
    return f"""MERGE INTO {db}.GOLD.FACT_SELLOUT AS target
USING (
    SELECT
        MD5(
            CONCAT(itm.invoice_number, '|', itm.partner_id, '|', itm.sku, '|', itm.batch_number)
        ) AS sellout_key,
        TO_NUMBER(TO_VARCHAR(inv.issue_date, 'YYYYMMDD')) AS date_key,
        MD5(itm.partner_id) AS partner_key,
        MD5(itm.sku) AS sku_key,
        itm.invoice_number,
        itm.batch_number,
        itm.quantity AS quantity_sold,
        itm.unit_price,
        itm.total_price,
        CASE
            WHEN inv.subtotal > 0
            THEN ROUND((itm.total_price / inv.subtotal) * inv.tax_amount, 2)
            ELSE 0.00
        END AS tax_amount,
        CASE
            WHEN inv.subtotal > 0
            THEN itm.total_price - ROUND((itm.total_price / inv.subtotal) * inv.tax_amount, 2)
            ELSE itm.total_price
        END AS net_revenue
    FROM {db}.SILVER.INVOICE_ITEMS itm
    JOIN {db}.SILVER.INVOICES inv
        ON itm.invoice_number = inv.invoice_number
        AND itm.partner_id = inv.partner_id
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY itm.invoice_number, itm.partner_id, itm.sku, itm.batch_number
        ORDER BY itm.transformed_at DESC
    ) = 1
) AS src
ON target.sellout_key = src.sellout_key
WHEN MATCHED THEN
    UPDATE SET
        target.date_key = src.date_key,
        target.partner_key = src.partner_key,
        target.sku_key = src.sku_key,
        target.quantity_sold = src.quantity_sold,
        target.unit_price = src.unit_price,
        target.total_price = src.total_price,
        target.tax_amount = src.tax_amount,
        target.net_revenue = src.net_revenue,
        target.transformed_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
    INSERT (
        sellout_key,
        date_key,
        partner_key,
        sku_key,
        invoice_number,
        batch_number,
        quantity_sold,
        unit_price,
        total_price,
        tax_amount,
        net_revenue,
        transformed_at
    )
    VALUES (
        src.sellout_key,
        src.date_key,
        src.partner_key,
        src.sku_key,
        src.invoice_number,
        src.batch_number,
        src.quantity_sold,
        src.unit_price,
        src.total_price,
        src.tax_amount,
        src.net_revenue,
        CURRENT_TIMESTAMP()
    )"""


def build_fact_inventory_snapshot_sql(database: str = "AURA_LAKEHOUSE") -> str:
    """Generate idempotent MERGE statement for GOLD.FACT_INVENTORY_SNAPSHOT.

    Resolves partner, sku, and date foreign surrogate keys from
    SILVER.PARTNER_INVENTORY records.

    Args:
        database: Target Snowflake database name.

    Returns:
        str: Formatted MERGE SQL query.
    """
    db = _sanitize_db(database)
    return f"""MERGE INTO {db}.GOLD.FACT_INVENTORY_SNAPSHOT AS target
USING (
    SELECT
        MD5(
            CONCAT(
                partner_id, '|', sku, '|', batch_id, '|',
                warehouse_location, '|', TO_VARCHAR(snapshot_date, 'YYYY-MM-DD')
            )
        ) AS snapshot_key,
        TO_NUMBER(TO_VARCHAR(snapshot_date, 'YYYYMMDD')) AS date_key,
        MD5(partner_id) AS partner_key,
        MD5(sku) AS sku_key,
        batch_id,
        warehouse_location,
        stock_quantity,
        snapshot_date
    FROM {db}.SILVER.PARTNER_INVENTORY
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY partner_id, sku, batch_id, warehouse_location, snapshot_date
        ORDER BY transformed_at DESC
    ) = 1
) AS src
ON target.snapshot_key = src.snapshot_key
WHEN MATCHED THEN
    UPDATE SET
        target.date_key = src.date_key,
        target.partner_key = src.partner_key,
        target.sku_key = src.sku_key,
        target.stock_quantity = src.stock_quantity,
        target.snapshot_date = src.snapshot_date,
        target.transformed_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
    INSERT (
        snapshot_key,
        date_key,
        partner_key,
        sku_key,
        batch_id,
        warehouse_location,
        stock_quantity,
        snapshot_date,
        transformed_at
    )
    VALUES (
        src.snapshot_key,
        src.date_key,
        src.partner_key,
        src.sku_key,
        src.batch_id,
        src.warehouse_location,
        src.stock_quantity,
        src.snapshot_date,
        CURRENT_TIMESTAMP()
    )"""


def build_fact_competitor_pricing_sql(database: str = "AURA_LAKEHOUSE") -> str:
    """Generate idempotent MERGE statement for GOLD.FACT_COMPETITOR_PRICING.

    Computes price_per_ml metrics and normalizes availability status flags
    from SILVER.COMPETITOR_PRICES observations.

    Args:
        database: Target Snowflake database name.

    Returns:
        str: Formatted MERGE SQL query.
    """
    db = _sanitize_db(database)
    return f"""MERGE INTO {db}.GOLD.FACT_COMPETITOR_PRICING AS target
USING (
    SELECT
        MD5(
            CONCAT(
                competitor_brand, '|', product_title, '|',
                TO_VARCHAR(observed_at, 'YYYY-MM-DD HH24:MI:SS')
            )
        ) AS pricing_key,
        TO_NUMBER(TO_VARCHAR(observed_at::DATE, 'YYYYMMDD')) AS date_key,
        competitor_brand,
        product_title,
        volume_ml,
        price_brl,
        ROUND(price_brl / NULLIF(volume_ml, 0), 4) AS price_per_ml,
        stock_status,
        CASE
            WHEN UPPER(stock_status) IN ('IN_STOCK', 'IN STOCK', 'AVAILABLE', 'TRUE') THEN TRUE
            ELSE FALSE
        END AS is_in_stock,
        observed_at,
        source_url
    FROM {db}.SILVER.COMPETITOR_PRICES
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY competitor_brand, product_title, observed_at
        ORDER BY transformed_at DESC
    ) = 1
) AS src
ON target.pricing_key = src.pricing_key
WHEN MATCHED THEN
    UPDATE SET
        target.date_key = src.date_key,
        target.volume_ml = src.volume_ml,
        target.price_brl = src.price_brl,
        target.price_per_ml = src.price_per_ml,
        target.stock_status = src.stock_status,
        target.is_in_stock = src.is_in_stock,
        target.source_url = src.source_url,
        target.transformed_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
    INSERT (
        pricing_key,
        date_key,
        competitor_brand,
        product_title,
        volume_ml,
        price_brl,
        price_per_ml,
        stock_status,
        is_in_stock,
        observed_at,
        source_url,
        transformed_at
    )
    VALUES (
        src.pricing_key,
        src.date_key,
        src.competitor_brand,
        src.product_title,
        src.volume_ml,
        src.price_brl,
        src.price_per_ml,
        src.stock_status,
        src.is_in_stock,
        src.observed_at,
        src.source_url,
        CURRENT_TIMESTAMP()
    )"""


def get_all_gold_dimension_queries(database: str = "AURA_LAKEHOUSE") -> dict[str, str]:
    """Retrieve all Gold dimension MERGE query definitions.

    Args:
        database: Target Snowflake database name.

    Returns:
        dict[str, str]: Mapping of dimension name to SQL query string.
    """
    return {
        "dim_date": build_dim_date_sql(database),
        "dim_partners": build_dim_partners_sql(database),
        "dim_skus": build_dim_skus_sql(database),
        "dim_hubs": build_dim_hubs_sql(database),
    }


def get_all_gold_fact_queries(database: str = "AURA_LAKEHOUSE") -> dict[str, str]:
    """Retrieve all Gold fact MERGE query definitions.

    Args:
        database: Target Snowflake database name.

    Returns:
        dict[str, str]: Mapping of fact name to SQL query string.
    """
    return {
        "fact_sellout": build_fact_sellout_sql(database),
        "fact_inventory_snapshot": build_fact_inventory_snapshot_sql(database),
        "fact_competitor_pricing": build_fact_competitor_pricing_sql(database),
    }


def get_all_gold_queries(database: str = "AURA_LAKEHOUSE") -> dict[str, str]:
    """Retrieve all Gold layer MERGE query definitions.

    Args:
        database: Target Snowflake database name.

    Returns:
        dict[str, str]: Combined mapping of all dimension and fact queries.
    """
    all_queries = get_all_gold_dimension_queries(database)
    all_queries.update(get_all_gold_fact_queries(database))
    return all_queries
