import io
import logging
from typing import Optional

from docx import Document
from pypdf import PdfReader

logger = logging.getLogger(__name__)

MAX_TEXT_CHARS = 200_000


def extract_text(file_bytes: bytes, filename: str) -> Optional[str]:
    """Extract plain text from a PDF, DOCX, TXT, or MD file."""
    lower_name = filename.lower()
    if lower_name.endswith(".pdf"):
        return _extract_pdf_text(file_bytes)
    if lower_name.endswith(".docx"):
        return _extract_docx_text(file_bytes)
    if lower_name.endswith(".txt") or lower_name.endswith(".md"):
        return file_bytes.decode("utf-8", errors="ignore")[:MAX_TEXT_CHARS]

    logger.warning("document_extractor.unsupported_type filename=%s", filename)
    return None


def _extract_pdf_text(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    parts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            parts.append(text)
    return "\n".join(parts)[:MAX_TEXT_CHARS]


def _extract_docx_text(file_bytes: bytes) -> str:
    doc = Document(io.BytesIO(file_bytes))
    parts = [para.text for para in doc.paragraphs]
    return "\n".join(parts)[:MAX_TEXT_CHARS]
