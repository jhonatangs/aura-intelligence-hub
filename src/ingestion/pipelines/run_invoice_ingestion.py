"""Pipeline CLI entrypoint for batch invoice generation, parsing, and Bronze ingestion.

Orchestrates synthetic partner invoice PDF generation, layout-preserving text extraction,
self-correcting LangGraph structured parsing, and persistence to Snowflake Bronze layer.
"""

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from src.ingestion.agents.invoice_graph import parse_invoice_document
from src.ingestion.generators.invoice_generator import generate_sample_invoices
from src.ingestion.parsers.pdf_reader import extract_pdf_text
from src.ingestion.repositories.bronze_invoice_repo import BronzeInvoiceRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("aura.ingestion.pipeline")


def run_pipeline(
    output_dir: Path | str = "data/raw/partners",
    generate_samples: int = 3,
    skip_generation: bool = False,
    dry_run: bool = False,
    max_retries: int = 3,
) -> int:
    """Execute the end-to-end partner invoice ingestion pipeline.

    Args:
        output_dir: Filesystem directory containing or receiving PDF invoices.
        generate_samples: Number of sample ERP PDFs to create if generation enabled.
        skip_generation: When True, bypasses generation and processes existing PDFs.
        dry_run: When True, validates and parses payloads without writing to Snowflake.
        max_retries: Maximum LangGraph self-correction retries per invoice.

    Returns:
        int: Return code (0 for complete success, 1 if any invoice failed).
    """
    target_dir = Path(output_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    if not skip_generation:
        logger.info(
            "Generating %d synthetic ERP partner invoices in %s...",
            generate_samples,
            target_dir,
        )
        generate_sample_invoices(target_dir, count=generate_samples)

    pdf_files = sorted(target_dir.glob("*.pdf"))
    if not pdf_files:
        logger.warning("No PDF invoices discovered in %s", target_dir)
        return 0

    logger.info("Found %d PDF invoice(s) to process", len(pdf_files))

    repo = None if dry_run else BronzeInvoiceRepository()
    total_processed = 0
    total_succeeded = 0
    total_failed = 0

    for pdf_path in pdf_files:
        total_processed += 1
        logger.info(
            "Processing invoice [%d/%d]: %s", total_processed, len(pdf_files), pdf_path.name
        )

        try:
            raw_text = extract_pdf_text(pdf_path)
            state = parse_invoice_document(raw_text, max_retries=max_retries)

            if not state.get("is_valid") or state.get("parsed_payload") is None:
                logger.error(
                    "Failed to parse invoice %s after %d retries. Errors: %s",
                    pdf_path.name,
                    state.get("retry_count", 0),
                    state.get("validation_errors", []),
                )
                total_failed += 1
                continue

            payload = state["parsed_payload"]
            partner_id = payload.metadata.partner_id
            logger.info(
                "Successfully parsed %s | Partner: %s | Total: R$ %.2f (retries: %d)",
                pdf_path.name,
                partner_id,
                payload.total_amount,
                state.get("retry_count", 0),
            )

            if dry_run or repo is None:
                logger.info(
                    "[DRY-RUN] Record ready for Bronze storage: %s (partner: %s)",
                    pdf_path.name,
                    partner_id,
                )
            else:
                logger.info("Inserting record into AURA_LAKEHOUSE.BRONZE.INVOICES_RAW...")
                repo.insert_invoice(
                    source_file=pdf_path.name,
                    partner_id=partner_id,
                    payload=payload,
                )
                logger.info("Successfully persisted %s to Snowflake Bronze", pdf_path.name)

            total_succeeded += 1

        except Exception as exc:
            logger.exception("Unexpected error processing invoice %s: %s", pdf_path.name, exc)
            total_failed += 1

    logger.info(
        "Ingestion summary: %d total, %d succeeded, %d failed",
        total_processed,
        total_succeeded,
        total_failed,
    )
    return 0 if total_failed == 0 else 1


def main(argv: Sequence[str] | None = None) -> None:
    """Command line interface entrypoint for invoice ingestion."""
    parser = argparse.ArgumentParser(
        description="Aura Intelligence Hub - Partner Invoice Ingestion Pipeline",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/raw/partners",
        help="Directory to store or scan for invoice PDFs (default: data/raw/partners)",
    )
    parser.add_argument(
        "--generate-samples",
        type=int,
        default=3,
        help="Number of synthetic sample PDFs to generate (default: 3)",
    )
    parser.add_argument(
        "--skip-generation",
        action="store_true",
        help="Skip generation of new PDFs and process existing files only",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run parsing without persisting records to Snowflake",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum LangGraph validation retries per document (default: 3)",
    )

    args = parser.parse_args(argv)
    exit_code = run_pipeline(
        output_dir=args.output_dir,
        generate_samples=args.generate_samples,
        skip_generation=args.skip_generation,
        dry_run=args.dry_run,
        max_retries=args.max_retries,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
