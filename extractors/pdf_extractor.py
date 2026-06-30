from __future__ import annotations

from schema.metadata import TechnicalMetadata, TechnicalMetadataPDF
from utils.cache import compute_checksum


def _fitz():
    try:
        import pymupdf
        return pymupdf
    except ImportError:
        pass
    try:
        import fitz
        return fitz
    except ImportError:
        raise ImportError(
            "PyMuPDF is not installed. Run: pip install PyMuPDF"
        )


def extract_pdf_metadata(file_bytes: bytes, filename: str) -> tuple[TechnicalMetadata, str]:
    """Return (TechnicalMetadata, extracted_text_for_llm)."""
    fitz = _fitz()
    checksum = compute_checksum(file_bytes)
    doc = fitz.open(stream=file_bytes, filetype="pdf")

    full_text = "".join(page.get_text() for page in doc)
    is_scanned = len(full_text.strip()) < 100

    if is_scanned:
        full_text = _ocr_fallback(file_bytes) or full_text

    word_count = len(full_text.split())

    pdf_meta = TechnicalMetadataPDF(
        page_count=len(doc),
        word_count=word_count,
        char_count=len(full_text),
        is_scanned=is_scanned,
        pdf_version=str(doc.metadata.get("format", "")),
        reading_time_min=round(word_count / 200, 1),
    )

    technical = TechnicalMetadata(
        file_name=filename,
        asset_type="unstructured",
        subtype="pdf",
        size_bytes=len(file_bytes),
        checksum_sha256=checksum,
        pdf=pdf_meta,
    )

    return technical, full_text[:4000]


def _ocr_fallback(file_bytes: bytes) -> str:
    try:
        import pytesseract
        from pdf2image import convert_from_bytes  # type: ignore

        images = convert_from_bytes(file_bytes)
        return "\n".join(pytesseract.image_to_string(img) for img in images)
    except Exception:
        return ""
