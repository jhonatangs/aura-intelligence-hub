"""Ingestion pipeline entrypoints."""

from src.ingestion.pipelines.run_invoice_ingestion import run_pipeline

__all__ = ["run_pipeline"]
