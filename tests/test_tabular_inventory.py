"""Unit tests for legacy tabular inventory parser."""

from datetime import date
from pathlib import Path

import pytest

from src.ingestion.parsers.tabular_inventory import (
    compute_md5,
    detect_delimiter,
    detect_encoding_and_decode,
    parse_date_flexible,
    parse_tabular_inventory_bytes,
    parse_tabular_inventory_file,
)


def test_compute_md5() -> None:
    """Verify deterministic MD5 computation."""
    content = b"sample inventory payload data"
    digest = compute_md5(content)
    assert len(digest) == 32
    assert digest == "a93a64dcbe555c9f42a9940ff6451732"


def test_detect_delimiter() -> None:
    """Verify delimiter detection for comma, semicolon, pipe, and tab."""
    assert detect_delimiter("partner_id,sku,batch_id,stock_quantity\n") == ","
    assert detect_delimiter("cd_parceiro;cod_sku;lote;saldo\n") == ";"
    assert detect_delimiter("partner|sku|batch|qty|location\n") == "|"
    assert detect_delimiter("partner\tsku\tbatch\tqty\n") == "\t"


def test_detect_encoding_and_decode() -> None:
    """Verify UTF-8 and Latin-1 decoding fallbacks."""
    utf8_bytes = "Aura Energy Tropical 250ml - São Paulo".encode()
    text_u, enc_u = detect_encoding_and_decode(utf8_bytes)
    assert enc_u == "utf-8"
    assert "São Paulo" in text_u

    latin1_bytes = "Armazém Distribuição".encode("latin-1")
    text_l, enc_l = detect_encoding_and_decode(latin1_bytes)
    assert "Distribuição" in text_l


def test_parse_date_flexible() -> None:
    """Verify flexible date parsing across common ERP conventions."""
    assert parse_date_flexible("2026-03-10") == date(2026, 3, 10)
    assert parse_date_flexible("10/03/2026") == date(2026, 3, 10)
    assert parse_date_flexible("2026/03/10") == date(2026, 3, 10)
    assert parse_date_flexible("20260310") == date(2026, 3, 10)


def test_parse_comma_delimited_standard(tmp_path: Path) -> None:
    """Verify parsing standard CSV file with canonical headers."""
    csv_content = """partner_id,sku,batch_id,stock_quantity,warehouse_location,snapshot_date
PARTNER_SP_01,AURA_250ML,BATCH-2026-001,1500,WH_SP_MAIN,2026-03-01
PARTNER_SP_01,AURA_ZERO_250ML,BATCH-2026-002,850,WH_SP_MAIN,2026-03-01
PARTNER_SP_01,AURA_TROPICAL_473ML,BATCH-2026-003,2400,WH_SP_MAIN,2026-03-01
"""
    file_path = tmp_path / "inventory_sp.csv"
    file_path.write_text(csv_content, encoding="utf-8")

    result = parse_tabular_inventory_file(file_path)

    assert result.total_rows == 3
    assert result.valid_rows == 3
    assert result.invalid_rows == 0
    assert result.delimiter == ","
    assert len(result.records) == 3
    assert result.records[0].sku == "AURA_250ML"
    assert result.records[0].stock_quantity == 1500
    assert result.records[2].stock_quantity == 2400
    assert result.file_hash_md5 == compute_md5(csv_content.encode("utf-8"))


def test_parse_semicolon_delimited_latin1_aliases(tmp_path: Path) -> None:
    """Verify parsing Brazilian ERP export with semicolon and localized headers."""
    content = """cd_parceiro;cod_sku;lote;saldo;armazem;data_posicao
DIST_RJ_COAST;AURA_250ML;LOT-RJ-88;3200;Galpão Caju;15/03/2026
DIST_RJ_COAST;AURA_TROPICAL_473ML;LOT-RJ-89;1800;Galpão Caju;15/03/2026
"""
    file_path = tmp_path / "inventory_rj.csv"
    file_path.write_bytes(content.encode("latin-1"))

    result = parse_tabular_inventory_file(file_path)

    assert result.total_rows == 2
    assert result.valid_rows == 2
    assert result.delimiter == ";"
    assert result.encoding == "latin-1"
    assert result.records[0].partner_id == "DIST_RJ_COAST"
    assert result.records[0].warehouse_location == "Galpão Caju"
    assert result.records[0].snapshot_date == date(2026, 3, 15)


def test_parse_pipe_delimited() -> None:
    """Verify parsing pipe-delimited format with compact date."""
    content = (
        b"partner_id|sku|batch_id|stock_quantity|warehouse_location|snapshot_date\n"
        b"PARTNER_BH|AURA_ZERO_250ML|BH-LOT-1|450|BH_NORTH|20260305\n"
    )
    result = parse_tabular_inventory_bytes(content, filename="inventory_bh.txt")

    assert result.total_rows == 1
    assert result.valid_rows == 1
    assert result.delimiter == "|"
    assert result.records[0].partner_id == "PARTNER_BH"
    assert result.records[0].snapshot_date == date(2026, 3, 5)


def test_invalid_rows_rejection_and_isolation() -> None:
    """Verify malformed rows are isolated into error logs while valid rows succeed."""
    content = b"""partner_id,sku,batch_id,stock_quantity,warehouse_location,snapshot_date
PARTNER_01,AURA_250ML,BATCH-1,500,WH-1,2026-03-01
PARTNER_01,,BATCH-2,300,WH-1,2026-03-01
PARTNER_01,AURA_ZERO_250ML,BATCH-3,-50,WH-1,2026-03-01
PARTNER_01,AURA_TROPICAL_473ML,BATCH-4,not_a_number,WH-1,2026-03-01
PARTNER_01,AURA_TROPICAL_473ML,BATCH-5,1200,WH-1,2026-03-01
"""

    result = parse_tabular_inventory_bytes(content)

    assert result.total_rows == 5
    assert result.valid_rows == 2
    assert result.invalid_rows == 3
    assert len(result.errors) == 3
    assert len(result.records) == 2
    assert result.records[0].sku == "AURA_250ML"
    assert result.records[1].sku == "AURA_TROPICAL_473ML"


def test_parse_file_not_found(tmp_path: Path) -> None:
    """Verify FileNotFoundError is raised when file does not exist."""
    missing = tmp_path / "non_existent.csv"
    with pytest.raises(FileNotFoundError):
        parse_tabular_inventory_file(missing)


def test_parse_empty_content() -> None:
    """Verify empty content returns zero records gracefully."""
    result = parse_tabular_inventory_bytes(b"", filename="empty.csv")
    assert result.total_rows == 0
    assert result.valid_rows == 0
    assert len(result.records) == 0
