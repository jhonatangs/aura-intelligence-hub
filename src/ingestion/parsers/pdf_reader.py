"""Layout-preserving PDF extraction utility with error boundary handling.

Extracts raw text streams and structured tokens from partner B2B invoices using
pypdf, isolating corrupted or malformed documents behind explicit error boundaries.
"""

from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class PdfExtractionError(Exception):
    """Raised when PDF document extraction encounters corrupted data or parsing errors."""


@dataclass(frozen=True)
class PdfDocumentContent:
    """Extracted content and layout metadata from a PDF file.

    Attributes:
        file_path: Origin path of the extracted PDF.
        page_count: Total number of pages processed.
        raw_text: Unified text string across all document pages.
        tokens: Whitespace-delimited token stream preserving sequential layout.
    """

    file_path: str
    page_count: int
    raw_text: str
    tokens: list[str]


def extract_pdf_document(pdf_path: Path | str) -> PdfDocumentContent:
    """Extract full text and tokens from a PDF file with error boundaries.

    Args:
        pdf_path: Filesystem path to the target PDF document.

    Returns:
        PdfDocumentContent: Extracted text, token streams, and page statistics.

    Raises:
        FileNotFoundError: If the specified path does not exist.
        PdfExtractionError: If the file is empty, corrupted, or an invalid PDF.
    """
    path = Path(pdf_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"PDF file does not exist: {path}")

    if not path.is_file():
        raise PdfExtractionError(f"Target path is not a file: {path}")

    if path.stat().st_size == 0:
        raise PdfExtractionError(f"PDF document is empty (0 bytes): {path}")

    try:
        reader = PdfReader(str(path))
        if len(reader.pages) == 0:
            raise PdfExtractionError(f"PDF document contains 0 pages: {path}")

        extracted_pages: list[str] = []
        for page in reader.pages:
            try:
                page_text = page.extract_text(extraction_mode="layout")
            except Exception:
                page_text = page.extract_text() or ""

            if not page_text:
                page_text = page.extract_text() or ""

            extracted_pages.append(page_text.strip())

        unified_text = "\n\n--- PAGE BREAK ---\n\n".join(extracted_pages).strip()
        tokens = [t for t in unified_text.split() if t]

        return PdfDocumentContent(
            file_path=str(path),
            page_count=len(reader.pages),
            raw_text=unified_text,
            tokens=tokens,
        )

    except (PdfReadError, ValueError, IndexError) as err:
        raise PdfExtractionError(f"Corrupted or invalid PDF document at '{path}': {err}") from err
    except PdfExtractionError:
        raise
    except Exception as err:
        raise PdfExtractionError(f"Unexpected failure reading PDF '{path}': {err}") from err


def extract_pdf_text(pdf_path: Path | str) -> str:
    """Convenience wrapper extracting unified raw text from a PDF file.

    Args:
        pdf_path: Path to the target PDF document.

    Returns:
        str: Cleaned text stream from all document pages.
    """
    doc = extract_pdf_document(pdf_path)
    return doc.raw_text
