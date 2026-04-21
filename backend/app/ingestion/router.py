"""
File purpose:
- Routes uploaded files to the correct loader based on file extension.
- Centralizes file-type dispatch so API code stays simple.
"""

from pathlib import Path
from typing import Any, Union
from urllib.parse import urlparse
from .loaders import (
    load_pdf,
    load_pdf_sections,
    load_docx,
    load_pptx,
    load_image,
    load_csv,
    load_json,
    load_xml,
    load_web,
)
from .text_cleaning import clean_sections, clean_text


def load_file(file_path: Union[str, Path]) -> str:
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        return load_pdf(file_path)

    elif suffix == ".docx":
        return load_docx(file_path)

    elif suffix == ".pptx":
        return load_pptx(file_path)

    elif suffix in [".png", ".jpg", ".jpeg"]:
        return load_image(file_path)

    elif suffix == ".csv":
        return load_csv(file_path)

    elif suffix == ".json":
        return load_json(file_path)

    elif suffix == ".xml":
        return load_xml(file_path)

    else:
        raise ValueError(f"Unsupported file type: {suffix}")


def load_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Invalid URL. Please provide a full http/https URL.")

    try:
        return clean_text(load_web(url))
    except Exception as exc:
        raise ValueError(f"Failed to load URL: {exc}") from exc


def load_file_with_metadata(file_path: Union[str, Path]) -> dict[str, Any]:
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        raw_sections = load_pdf_sections(file_path)
        sections = clean_sections(
            [
                {"page_number": int(section["page_number"]), "text": str(section["text"])}
                for section in raw_sections
            ],
            text_key="text",
        )
        text = "\n".join(section["text"] for section in sections)
        page_numbers = [section["page_number"] for section in sections if section["text"]]
    else:
        text = clean_text(load_file(file_path))
        page_numbers = []

    return {
        "text": text,
        "metadata": {
            "document_name": file_path.name,
            "file_type": suffix.lstrip("."),
            "page_numbers": page_numbers,
        },
    }


def load_url_with_metadata(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Invalid URL. Please provide a full http/https URL.")

    try:
        text = clean_text(load_web(url))
    except Exception as exc:
        raise ValueError(f"Failed to load URL: {exc}") from exc

    return {
        "text": text,
        "metadata": {
            "document_name": parsed.netloc,
            "file_type": "url",
            "source_url": url,
            "page_numbers": [],
        },
    }
