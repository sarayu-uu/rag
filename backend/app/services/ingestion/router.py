"""
File purpose:
- Routes uploaded files to the correct loader based on file extension.
- Centralizes file-type dispatch so API code stays simple.
"""

from pathlib import Path
from typing import Union
from urllib.parse import urlparse
from .loaders import (
    load_pdf,
    load_docx,
    load_pptx,
    load_image,
    load_csv,
    load_json,
    load_web,
)


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

    else:
        raise ValueError(f"Unsupported file type: {suffix}")


def load_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Invalid URL. Please provide a full http/https URL.")

    try:
        return load_web(url)
    except Exception as exc:
        raise ValueError(f"Failed to load URL: {exc}") from exc
