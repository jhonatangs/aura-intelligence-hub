"""Tabular inventory file parser for legacy partner ERP extracts.

Supports automatic delimiter detection (;, ,, |), encoding fallback (utf-8, latin1),
MD5 content hashing, and normalization into PartnerInventoryRecord models.
"""

import csv
import hashlib
import io
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from src.ingestion.models.multimodal import PartnerInventoryRecord

logger = logging.getLogger(__name__)

# Column aliases normalization mapping
COLUMN_ALIASES: dict[str, str] = {
    # Partner identifier
    "partner_id": "partner_id",
    "partner": "partner_id",
    "cd_parceiro": "partner_id",
    "distributor_id": "partner_id",
    "id_distribuidor": "partner_id",
    "cod_distribuidor": "partner_id",
    # SKU
    "sku": "sku",
    "cod_sku": "sku",
    "product_code": "sku",
    "codigo_produto": "sku",
    "produto": "sku",
    "item": "sku",
    # Batch / Lot
    "batch_id": "batch_id",
    "batch": "batch_id",
    "lote": "batch_id",
    "numero_lote": "batch_id",
    "num_lote": "batch_id",
    "lot": "batch_id",
    # Stock quantity
    "stock_quantity": "stock_quantity",
    "stock": "stock_quantity",
    "quantity": "stock_quantity",
    "quantidade": "stock_quantity",
    "saldo": "stock_quantity",
    "qtd": "stock_quantity",
    "qty": "stock_quantity",
    "estoque": "stock_quantity",
    # Warehouse location
    "warehouse_location": "warehouse_location",
    "warehouse": "warehouse_location",
    "location": "warehouse_location",
    "local": "warehouse_location",
    "armazem": "warehouse_location",
    "deposito": "warehouse_location",
    "depósito": "warehouse_location",
    "filial": "warehouse_location",
    # Snapshot date
    "snapshot_date": "snapshot_date",
    "date": "snapshot_date",
    "data": "snapshot_date",
    "data_posicao": "snapshot_date",
    "data_saldo": "snapshot_date",
    "dt_posicao": "snapshot_date",
    "dt_saldo": "snapshot_date",
}


@dataclass(frozen=True)
class TabularParseResult:
    """Result payload from tabular inventory parsing.

    Attributes:
        records: Successfully validated PartnerInventoryRecord instances.
        file_hash_md5: MD5 hex digest of the raw byte stream.
        delimiter: Detected delimiter character.
        encoding: Detected encoding used to decode content.
        total_rows: Total tabular data rows encountered.
        valid_rows: Number of successfully parsed records.
        invalid_rows: Number of rejected or malformed rows.
        errors: Error messages encountered during row processing.
    """

    records: list[PartnerInventoryRecord] = field(default_factory=list)
    file_hash_md5: str = ""
    delimiter: str = ","
    encoding: str = "utf-8"
    total_rows: int = 0
    valid_rows: int = 0
    invalid_rows: int = 0
    errors: list[str] = field(default_factory=list)


def compute_md5(data: bytes) -> str:
    """Compute hexadecimal MD5 hash for byte payload.

    Args:
        data: Raw file bytes.

    Returns:
        str: 32-character lowercase hex digest.
    """
    return hashlib.md5(data).hexdigest()


def detect_encoding_and_decode(data: bytes) -> tuple[str, str]:
    """Decode bytes by attempting UTF-8 first, falling back to Latin-1.

    Args:
        data: Raw byte payload.

    Returns:
        tuple[str, str]: (Decoded text string, encoding used).
    """
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return data.decode("latin-1"), "latin-1"


def detect_delimiter(text_sample: str) -> str:
    """Detect delimiter among standard candidates (;, ,, |) from text sample.

    Args:
        text_sample: First lines of the delimited file.

    Returns:
        str: Detected delimiter character.
    """
    candidate_delimiters = [";", ",", "|", "\t"]
    first_line = text_sample.strip().splitlines()[0] if text_sample.strip() else ""

    counts = {delim: first_line.count(delim) for delim in candidate_delimiters}
    best_delim = max(counts, key=lambda k: counts[k])

    return best_delim if counts[best_delim] > 0 else ","


def parse_date_flexible(val: str) -> date:
    """Parse various date formats common across legacy ERP exports.

    Supported formats:
        - '2026-03-10' (ISO 8601)
        - '10/03/2026' (Brazilian format DD/MM/YYYY)
        - '2026/03/10'
        - '20260310' (Compact YYYYMMDD)

    Args:
        val: Raw date string.

    Returns:
        date: Standard datetime.date object.

    Raises:
        ValueError: If none of the date patterns match.
    """
    clean_val = val.strip()
    patterns = [
        ("%Y-%m-%d", r"^\d{4}-\d{2}-\d{2}$"),
        ("%d/%m/%Y", r"^\d{1,2}/\d{1,2}/\d{4}$"),
        ("%Y/%m/%d", r"^\d{4}/\d{2}/\d{2}$"),
        ("%Y%m%d", r"^\d{8}$"),
    ]

    for fmt, regex in patterns:
        if re.match(regex, clean_val):
            return datetime.strptime(clean_val, fmt).date()

    # Fallback to general fromisoformat
    return date.fromisoformat(clean_val)


def normalize_header(raw_header: str) -> str:
    """Normalize raw header name to standard domain field name."""
    clean = re.sub(r"[^\w]", "_", raw_header.strip().lower()).strip("_")
    return COLUMN_ALIASES.get(clean, clean)


def parse_tabular_inventory_bytes(
    content: bytes,
    filename: str = "",
    partner_id_fallback: str | None = None,
    snapshot_date_fallback: date | None = None,
) -> TabularParseResult:
    """Parse raw bytes representing a legacy tabular inventory extract.

    Args:
        content: Raw file bytes.
        filename: Optional filename identifier for logging and error reporting.
        partner_id_fallback: Optional partner ID applied if column is missing.
        snapshot_date_fallback: Optional date applied if date column is missing.

    Returns:
        TabularParseResult: Summary of parsing outcome including valid models.
    """
    file_hash = compute_md5(content)
    text_content, detected_encoding = detect_encoding_and_decode(content)

    if not text_content.strip():
        logger.warning("Encountered empty tabular inventory file '%s'", filename)
        return TabularParseResult(
            file_hash_md5=file_hash,
            encoding=detected_encoding,
            delimiter=",",
            total_rows=0,
            valid_rows=0,
            invalid_rows=0,
        )

    delimiter = detect_delimiter(text_content[:2048])
    reader = csv.reader(io.StringIO(text_content), delimiter=delimiter)

    try:
        raw_headers = next(reader)
    except StopIteration:
        return TabularParseResult(
            file_hash_md5=file_hash,
            encoding=detected_encoding,
            delimiter=delimiter,
            total_rows=0,
            valid_rows=0,
            invalid_rows=0,
        )

    normalized_headers = [normalize_header(h) for h in raw_headers]
    header_indices = {name: idx for idx, name in enumerate(normalized_headers)}

    records: list[PartnerInventoryRecord] = []
    errors: list[str] = []
    total_rows = 0
    valid_rows = 0
    invalid_rows = 0

    def _get_cell(current_row: Sequence[str], field_name: str, default: Any = None) -> Any:
        idx = header_indices.get(field_name)
        if idx is not None and idx < len(current_row):
            val = current_row[idx].strip()
            return val if val else default
        return default

    for row_num, row in enumerate(reader, start=2):
        if not row or all(not cell.strip() for cell in row):
            continue
        total_rows += 1

        try:
            partner_val = _get_cell(row, "partner_id", partner_id_fallback)
            sku_val = _get_cell(row, "sku")
            batch_val = _get_cell(row, "batch_id")
            qty_raw = _get_cell(row, "stock_quantity")
            loc_val = _get_cell(row, "warehouse_location", "DEFAULT_WH")
            date_raw = _get_cell(row, "snapshot_date")

            if not partner_val:
                raise ValueError(f"Row {row_num}: missing partner_id")
            if not sku_val:
                raise ValueError(f"Row {row_num}: missing sku")
            if not batch_val:
                raise ValueError(f"Row {row_num}: missing batch_id")
            if qty_raw is None:
                raise ValueError(f"Row {row_num}: missing stock_quantity")

            # Parse quantity (handle strings with dots or commas)
            clean_qty = str(qty_raw).replace(".", "").replace(",", "")
            quantity = int(clean_qty)

            # Parse date
            if date_raw:
                snapshot_date = parse_date_flexible(str(date_raw))
            elif snapshot_date_fallback:
                snapshot_date = snapshot_date_fallback
            else:
                snapshot_date = date.today()

            record = PartnerInventoryRecord(
                partner_id=str(partner_val),
                sku=str(sku_val),
                batch_id=str(batch_val),
                stock_quantity=quantity,
                warehouse_location=str(loc_val),
                snapshot_date=snapshot_date,
            )
            records.append(record)
            valid_rows += 1

        except (ValidationError, ValueError, Exception) as exc:
            invalid_rows += 1
            err_msg = f"Row {row_num} invalid: {exc}"
            errors.append(err_msg)
            logger.debug(err_msg)

    logger.info(
        "Parsed %s (hash=%s, enc=%s, delim='%s'): %d valid, %d invalid rows",
        filename or "stream",
        file_hash[:8],
        detected_encoding,
        delimiter,
        valid_rows,
        invalid_rows,
    )

    return TabularParseResult(
        records=records,
        file_hash_md5=file_hash,
        delimiter=delimiter,
        encoding=detected_encoding,
        total_rows=total_rows,
        valid_rows=valid_rows,
        invalid_rows=invalid_rows,
        errors=errors,
    )


def parse_tabular_inventory_file(
    file_path: Path | str,
    partner_id_fallback: str | None = None,
    snapshot_date_fallback: date | None = None,
) -> TabularParseResult:
    """Parse a tabular inventory file from the local filesystem.

    Args:
        file_path: Absolute or relative Path to CSV/TXT file.
        partner_id_fallback: Optional partner identifier fallback.
        snapshot_date_fallback: Optional date fallback.

    Returns:
        TabularParseResult: Parse result structure.

    Raises:
        FileNotFoundError: If the target file does not exist.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Inventory tabular file not found: {path}")

    content = path.read_bytes()
    return parse_tabular_inventory_bytes(
        content=content,
        filename=path.name,
        partner_id_fallback=partner_id_fallback,
        snapshot_date_fallback=snapshot_date_fallback,
    )
