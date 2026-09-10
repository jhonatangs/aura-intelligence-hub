"""Snowflake infrastructure bootstrapping script.

Parses and executes idempotent SQL DDL statements sequentially from
scripts/init_snowflake.sql using the SnowflakeClient context manager.
"""

import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path for direct script execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.common.snowflake_client import SnowflakeClient  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("bootstrap_snowflake")


def parse_sql_statements(sql_content: str) -> list[str]:
    """Parse raw SQL content into individual executable SQL statements.

    Strips inline and line comments and splits on semicolons, omitting
    empty statements.

    Args:
        sql_content: Raw SQL script text.

    Returns:
        list[str]: Sequence of non-empty SQL statements.
    """
    clean_lines: list[str] = []
    for raw_line in sql_content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("--"):
            continue
        clean_lines.append(line)

    combined_sql = " ".join(clean_lines)
    raw_statements = combined_sql.split(";")
    return [stmt.strip() for stmt in raw_statements if stmt.strip()]


def bootstrap_snowflake(sql_file_path: Path | None = None) -> None:
    """Bootstrap Snowflake Lakehouse infrastructure using init_snowflake.sql.

    Args:
        sql_file_path: Optional explicit path to the SQL initialization file.
            Defaults to scripts/init_snowflake.sql.

    Raises:
        FileNotFoundError: If the SQL init file does not exist.
        Exception: If any statement execution fails.
    """
    target_file = sql_file_path or (PROJECT_ROOT / "scripts" / "init_snowflake.sql")
    if not target_file.is_file():
        raise FileNotFoundError(f"SQL file not found at: {target_file}")

    logger.info("Reading SQL statements from %s", target_file)
    sql_text = target_file.read_text(encoding="utf-8")
    statements = parse_sql_statements(sql_text)
    logger.info("Discovered %d executable SQL statements", len(statements))

    with SnowflakeClient() as client:
        with client.managed_cursor() as cursor:
            for idx, stmt in enumerate(statements, start=1):
                preview = stmt[:60].replace("\n", " ") + ("..." if len(stmt) > 60 else "")
                logger.info("Executing statement [%d/%d]: %s", idx, len(statements), preview)
                cursor.execute(stmt)

    logger.info("Successfully bootstrapped Snowflake Lakehouse infrastructure.")


if __name__ == "__main__":
    bootstrap_snowflake()
